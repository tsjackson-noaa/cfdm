import copy
import re
import operator
import struct

from collections import OrderedDict

import numpy

from ..functions import abspath, flat

class ReadNetCDF(object):
    '''
    '''
    def __init__(self, NetCDF=None, AuxiliaryCoordinate=None,
                 CellMeasure=None, CellMethod=None,
                 CoordinateAncillary=None ,CoordinateReference=None,
                 DimensionCoordinate=None, DomainAncillary=None,
                 DomainAxis=None, Field=None, FieldAncillary=None,
                 Bounds=None, Data=None, GatheredArray=None):
        '''
        '''
        self._Bounds              = Bounds
        self._CoordinateAncillary = CoordinateAncillary
        self._Data                = Data
        self._NetCDF              = NetCDF
        self._GatheredArray       = GatheredArray

        # CF data model constructs
        self._AuxiliaryCoordinate = AuxiliaryCoordinate
        self._CellMeasure         = CellMeasure
        self._CellMethod          = CellMethod
        self._CoordinateReference = CoordinateReference
        self._DimensionCoordinate = DimensionCoordinate
        self._DomainAncillary     = DomainAncillary
        self._DomainAxis          = DomainAxis
        self._Field               = Field         
        self._FieldAncillary      = FieldAncillary
 
        # ------------------------------------------------------------
        # Initialise netCDF read parameters
        # ------------------------------------------------------------
        self._read_vars = {
            #
            'new_dimensions': {},
            #
            'formula_terms': {},
            #
            'compression': {},
            # Flag on whether or not to uncompress compressed variables
            'uncompress' : True,
            #
            'external_nc': [],
            # Chatty?
            'verbose': False,
            # Debug  print statements?
            '_debug': False,
        }
            
    @classmethod    
    def is_netcdf_file(cls, filename):
        '''Return True if the file is a netCDF file.
    
Note that the file type is determined by inspecting the file's
contents and any file suffix is not not considered.

:Parameters:

    filename: `str`

:Returns:

    out: `bool`

:Examples:

>>> is_netcdf_file('myfile.nc')
True
>>> is_netcdf_file('myfile.pp')
False
>>> is_netcdf_file('myfile.pdf')
False
>>> is_netcdf_file('myfile.txt')
False

        '''
        # Assume that URLs are in netCDF format
        if filename.startswith('http://'):
            return True

        # Read the magic number 
        try:
            fh = open(filename, 'rb')
            magic_number = struct.unpack('=L', fh.read(4))[0]
        except:
            magic_number = None
    
        try:
            fh.close()
        except:
            pass
    
        if magic_number in (21382211, 1128547841, 1178880137, 38159427):
            return True
        else:
            return False
    #--- End: def

    def read(self, filename, field=(), verbose=False, uncompress=True,
             extra_read_vars=None, _debug=False):
        '''Read fields from a netCDF file on disk or from an OPeNDAP server
location.

The file may be big or little endian.

NetCDF dimension names are stored in the `ncdim` attributes of the
field's DomainAxis objects and netCDF variable names are stored in the
`ncvar` attributes of the field and its components (coordinates,
coordinate bounds, cell measures and coordinate references, domain
ancillaries, field ancillaries).

:Parameters:

    filename: `str` or `file`
        A string giving the file name or OPenDAP URL, or an open file
        object, from which to read fields. Note that if a file object
        is given it will be closed and reopened.

    field: sequence of `str`, optional
        Create independent fields from field components. The *field*
        parameter may be one, or a sequence, of:

          ======================  ====================================
          *field*                 Field components
          ======================  ====================================
          ``'field_ancillary'``   Field ancillary objects
          ``'domain_ancillary'``  Domain ancillary objects
          ``'dimension'``         Dimension coordinate objects
          ``'auxiliary'``         Auxiliary coordinate objects
          ``'measure'``           Cell measure objects
          ``'all'``               All of the above
          ======================  ====================================

            *Example:*
              To create fields from auxiliary coordinate objects:
              ``field=['auxiliary']``.

            *Example:*
              To create fields from domain ancillary and cell measure
              objects: ``field=['domain_ancillary', 'measure']``.

    verbose: `bool`, optional
        If True then print information to stdout.
    
:Returns:

    out: `list`
        The fields in the file.

:Examples:

>>> f = cf.netcdf.read('file.nc')
>>> type(f)
<class 'cf.field.FieldList'>
>>> f
[<CF Field: pmsl(30, 24)>,
 <CF Field: z-squared(17, 30, 24)>,
 <CF Field: temperature(17, 30, 24)>,
 <CF Field: temperature_wind(17, 29, 24)>]

>>> cf.netcdf.read('file.nc')[0:2]
[<CF Field: pmsl(30, 24)>,
 <CF Field: z-squared(17, 30, 24)>]

>>> cf.netcdf.read('file.nc', units='K')
[<CF Field: temperature(17, 30, 24)>,
 <CF Field: temperature_wind(17, 29, 24)>]

>>> cf.netcdf.read('file.nc')[0]
<CF Field: pmsl(30, 24)>

        '''
        self.read_vars = self._reset_read_vars(extra_read_vars)
        g = self.read_vars

        g['references'] = {}
        
        if isinstance(filename, file):
            name = filename.name
            filename.close()
            filename = name

        self._messages = {}

        g['uncompress'] = uncompress
        g['verbose']    = verbose
        g['_debug']     = _debug

        g['domain_ancillaries']    = {}
        g['field_ancillaries']     = {}
        g['dimension_coordinates'] = {}
        g['auxiliary_coordinates'] = {}
        g['cell_measures']         = {}

        g['do_not_create_field']   = set()

        compression = {}
        
        # ----------------------------------------------------------------
        # Parse field parameter
        # ----------------------------------------------------------------
        try:
            iter(field)
        except TypeError:
            raise ValueError(
                "Can't read: Bad parameter value: field={!r}".format(field))
               
        if 'all' in field:
            field = set(('domain_ancillary', 'field_ancillary',
                         'dimension_coordinate', 'auxiliary_coordinate',
                         'cell_measure'))
    
        g['fields']    = field
        g['promoted'] = []
        
        filename = abspath(filename)
        g['filename'] = filename

        # ------------------------------------------------------------
        # Open the netCDF file to be read
        # ------------------------------------------------------------
        nc = self.open_file()
        g['nc'] = nc
        
        if _debug:
            print 'Reading netCDF file:', filename
            print '    Input netCDF dataset =',nc
    
        # Set of all of the netCDF variable names in the file.
        #
        # For example:
        # >>> variables
        # set(['lon','lat','tas'])
        variables = set(map(str, nc.variables))
    
        # ----------------------------------------------------------------
        # Put the file's global attributes into the global
        # 'global_attributes' dictionary
        # ----------------------------------------------------------------
        global_attributes = {}
        for attr in map(str, nc.ncattrs()):
            try:
                value = nc.getncattr(attr)
                if isinstance(value, basestring):
                    try:
                        global_attributes[attr] = str(value)
                    except UnicodeEncodeError:
                        global_attributes[attr] = value.encode(errors='ignore')          
                else:
                    global_attributes[attr] = value     
            except UnicodeDecodeError:
                pass
        #--- End: for
        g['global_attributes'] = global_attributes
        if _debug:
            print '    global attributes:', g['global_attributes']
            
        # ----------------------------------------------------------------
        # Create a dictionary keyed by netCDF variable names where
        # each key's value is a dictionary of that variable's nc
        # attributes. E.g. attributes['tas']['units']='K'
        # ----------------------------------------------------------------
        attributes = {}
        for ncvar in variables:
            attributes[ncvar] = {}
            for attr in map(str, nc.variables[ncvar].ncattrs()):
                try:
                    attributes[ncvar][attr] = nc.variables[ncvar].getncattr(attr)
                    if isinstance(attributes[ncvar][attr], basestring):
                        try:
                            attributes[ncvar][attr] = str(attributes[ncvar][attr])
                        except UnicodeEncodeError:
                            attributes[ncvar][attr] = attributes[ncvar][attr].encode(errors='ignore')
                except UnicodeDecodeError:
                    pass
            #--- End: for
        #--- End: for
    
        nc_dimensions = map(str, nc.dimensions)
        if _debug:
            print '    netCDF dimensions:', nc_dimensions
    
        # ------------------------------------------------------------
        # List variables
        # ------------------------------------------------------------
        for ncvar in attributes:
            if tuple(nc.variables[ncvar].dimensions) == (ncvar,):
                compress = attributes[ncvar].get('compress')
                if compress is not None:
                    # This variable is a list variable for gathering arrays
                    self._parse_compression_gathered(ncvar, compress)
#                    self._reference(ncvar)
                    g['do_not_create_field'].add(ncvar)
        #--- End: for

        # ------------------------------------------------------------
        # DSG variables
        # ------------------------------------------------------------
        featureType = g['global_attributes'].get('featureType')
        if featureType is not None:
            g['featureType'] = featureType
            
            sample_dimension = None
            for ncvar in attributes:
                if attributes[ncvar].get('sample_dimension') is not None:
                    # This variable is a count variable for DSG contiguous
                    # ragged arrays
                    sample_dimension = attributes[ncvar]['sample_dimension']
                    cf_compliant = self._check_sample_dimension(ncvar,
                                                                sample_dimension)
                    if not cf_compliant:
                        sample_dimension = None
                    else:
                        element_dimension_2 = self._parse_DSG_contiguous_compression(
                            ncvar,
                            attributes,
                            sample_dimension)
                        #                        self._reference(ncvar)
                        g['do_not_create_field'].add(ncvar)
          #--- End: for

            instance_dimension = None
            for ncvar in attributes:
                                
                if attributes[ncvar].get('instance_dimension') is not None:
                    # This variable is an index variable for DSG indexed
                    # ragged arrays
                    instance_dimension = attributes[ncvar]['instance_dimension']
                    cf_compliant = self._check_instance_dimension(ncvar,
                                                                  instance_dimension)
                    if not cf_compliant:
                        instance_dimension = None
                    else:
                        element_dimension_1 = self._parse_DSG_indexed_compression(
                            ncvar,
                            attributes,
                            instance_dimension)
                        self._reference(ncvar)
                        g['do_not_create_field'].add(ncvar)
            #--- End: for
            print 'sample_dimension, instance_dimension =',sample_dimension, instance_dimension
            if (sample_dimension   is not None and
                instance_dimension is not None):
                
                self._parse_DSG_indexed_contiguous_compression(                
                        sample_dimension,
                        instance_dimension)
        #--- End: if
        
        fields = OrderedDict()
        for ncvar in variables:
            if ncvar in g['do_not_create_field']:
                continue

            fields[ncvar] = self._create_field(ncvar, attributes, verbose=verbose)
        #--- End: for
        
        got = []

        # 
        fields_in_file = []
        for ncvar, field in fields.iteritems():
            if self._is_unreferenced(ncvar):
                fields_in_file.append(field)
                got.append(ncvar)
            elif _debug:
                print '   ', ncvar, 'not a field'
        #--- End: for
        
        # Promote non-field constructs to field constructs
        for xx in g['fields']:
            for ncvar, f in fields.iteritems():
                for construct in getattr(f, xx+'s')().values():
                    ncvar = self._get_ncvar(construct)
                    if ncvar not in got:
                        fields_in_file.append(fields[ncvar])
                        got.append(ncvar)
        #--- End: for
                
        if _debug:
            print fields_in_file
            for x in fields_in_file:
                print x

        # ------------------------------------------------------------        
        # Close the netCDF file
        # ------------------------------------------------------------                
        self.close_file()
        
        return fields_in_file
    #--- End: def

    def close_file(self):
        '''Close the netCDF that has been read.

:Returns:

    None

        '''
        nc = self.read_vars['nc']
        nc.close()
    #--- End: def
        
    @classmethod
    def file_type(cls, filename):
        '''Find the format of a file.
    
:Parameters:
    
    filename: `str`
        The file name.
    
:Returns:
 
    out: `str`
        The format type of the file.
    
:Examples:

>>> filetype = file_type(filename)
    
    '''
        # ----------------------------------------------------------------
        # Assume that URLs are in netCDF format
        # ----------------------------------------------------------------
        if filename.startswith('http://'):
           return 'netCDF'
    
        # ----------------------------------------------------------------
        # netCDF
        # ----------------------------------------------------------------
        if netcdf.is_netcdf_file(filename):
            return 'netCDF'
    #--- End: def

    def open_file(self):
        '''Open the netCDf file for reading.

:Returns:

    out: `netCDF.Dataset`

        '''
        filename = self.read_vars['filename']
        return self._NetCDF.file_open(filename, 'r')
    #--- End: def        

    def _is_unreferenced(self, ncvar):
        '''Return True if the netCDF variable is unfeferenced by any other
netCDF variable.

:Examples 1:

>>> x = r._is_unreferenced('tas')

:Parameters:

    ncvar: `str`
        The netCDf variable name.

:Returns:

    out: `bool`
        '''
        return self.read_vars['references'].get(ncvar, 0) <= 0
    #--- End: def
    
    def _reset_read_vars(self, extra_read_vars):
        '''
        '''
        d = copy.deepcopy(self._read_vars)
        if extra_read_vars:
            d.update(copy.deepcopy(extra_read_vars))

        return d
    #--- End: def

    def _parse_compression_gathered(self, ncvar, compress):
        '''
        '''
        g = self.read_vars
        _debug = g['_debug']
        if _debug:
            print '        List variable: compress =', compress
    
        gathered_ncdimension = g['nc'].variables[ncvar].dimensions[0]

        parsed_compress = self._parse_y(ncvar, compress)
        cf_compliant = self._check_compress(ncvar, compress, parsed_compress)
        if not cf_compliant:
            return
            
        compression_type = 'gathered'
        indices = self._create_data(ncvar, uncompress_override=True)
        
        g['compression'][gathered_ncdimension] = {
            'gathered': {'indices'             : indices,
                         'implied_ncdimensions': parsed_compress}}
    #--- End: def
    
    def _parse_DSG_contiguous_compression(self, ncvar, attributes,
                                          sample_dimension):
        '''

:Parameters:

    ncvar: `str`
        The netCDF variable name of the DSG count variable.

    attributes: `dict`

    sample_dimension: `str`
        The netCDF dimension name of the DSG sample dimension.

:Returns:

    out: `str`
        The made-up netCDF dimension name of the DSG element dimension.

    '''
        g = self.read_vars        

        _debug = g['_debug']
        if _debug:
            print '    DSG count variable: sample_dimension =', sample_dimension

        variable = g['nc'].variables[ncvar]
        instance_dimension = variable.dimensions[0] 
        
        elements_per_instance = self._create_data(ncvar, uncompress_override=True)
    
        instance_dimension_size = elements_per_instance.size    
        element_dimension_size  = int(elements_per_instance.max())
    
        if _debug:
            print '    DSG contiguous array implied shape:', (instance_dimension_size,element_dimension_size)
    
        # Make up a netCDF dimension name for the element dimension
        featureType = g['featureType']
        if featureType in ('timeSeries', 'trajectory', 'profile'):
            element_dimension = featureType.lower()
        elif featureType == 'timeSeriesProfile':
            element_dimension = 'profile'
        elif featureType == 'trajectoryProfile':
            element_dimension = 'profile'
        else:
            element_dimension = 'element'
        if _debug:        
            print '    featureType =', featureType
    
        base = element_dimension
        n = 0
        while (element_dimension in g['nc'].dimensions or
               element_dimension in g['new_dimensions']):
            n += 1
            element_dimension = '{0}_{1}'.format(base, n)

        g['compression'].setdefault(sample_dimension, {})['DSG_contiguous'] = {
            'elements_per_instance'  : elements_per_instance,
            'implied_ncdimensions'   : (instance_dimension,
                                        element_dimension),
            'profile_ncdimension'    : instance_dimension,
            'element_dimension'      : element_dimension,
            'element_dimension_size' : element_dimension_size,
            'instance_dimension_size': instance_dimension_size,
            'instance_axis'          : 0,
            'instance_index'         : 0,
            'c_element_axis'         : 1,
        }
    
        g['new_dimensions'][element_dimension] = element_dimension_size
        
        if _debug:
            print "    Creating g['compression'][{!r}]['DSG_contiguous']".format(
                sample_dimension)
    
        return element_dimension
    #--- End: def
    
    def _parse_DSG_indexed_compression(self, ncvar, attributes,
                                       instance_dimension):
        '''
        ncvar: `str`
            The netCDF variable name of the DSG index variable.
    
        attributes: `dict`
    
        instance_dimension: `str`
            The netCDF variable name of the DSG instance dimension.
    
        '''
        g = self.read_vars
                
        _debug = g['_debug']
        if _debug:
            print '    DSG index variable: instance_dimension =', instance_dimension
        
        variable = g['nc'].variables[ncvar]

        index = self._create_data(ncvar, uncompress_override=True)

        (instance, inverse, count) = numpy.unique(index.get_array(),
                                                  return_inverse=True,
                                                  return_counts=True)

        # The indices of the sample dimension which apply to each
        # instance. For example, if the sample dimension has size 20
        # and there are 3 instances then the instances array might
        # look like [1, 0, 2, 2, 1, 0, 2, 1, 0, 0, 2, 1, 2, 2, 1, 0,
        # 0, 0, 2, 0].
        instances = self._create_Data(array=inverse)

        # The number of elements per instance. For the instances array
        # example above, the elements_per_instance array is [7, 5, 7].
        elements_per_instance = self._create_Data(array=count)
    
        instance_dimension_size = g['nc'].dimensions[instance_dimension].size
        element_dimension_size  = int(elements_per_instance.max())
    
        # Make up a netCDF dimension name for the element dimension
        featureType = g['featureType']
        if featureType in ('timeSeries', 'trajectory', 'profile'):
            element_dimension = featureType.lower()
        elif featureType == 'timeSeriesProfile':
            element_dimension = 'timeseries'
        elif featureType == 'trajectoryProfile':
            element_dimension = 'trajectory'
        else:
            element_dimension = 'element'
        if _debug:        
            print '    featureType =', featureType
    
        base = element_dimension
        n = 0
        while (element_dimension in g['nc'].dimensions or
               element_dimension in g['new_dimensions']):
            n += 1
            element_dimension = '{0}_{1}'.format(base, n)
            
        indexed_sample_dimension = g['nc'][ncvar].dimensions[0]
        
        g['compression'].setdefault(indexed_sample_dimension, {})['DSG_indexed'] = {
#            'empty_data'             : data,
            'elements_per_instance'  : elements_per_instance,
            'instances'              : instances,
            'implied_ncdimensions'   : (instance_dimension,
                                        element_dimension),
            'element_dimension'      : element_dimension,
            'instance_dimension_size': instance_dimension_size,
            'element_dimension_size' : element_dimension_size,
        }
    
        g['new_dimensions'][element_dimension] = element_dimension_size
        
        if _debug:
            print "    Created g['compression'][{!r}]['DSG_indexed']".format(
                indexed_sample_dimension)
    
        return element_dimension
    #--- End: def
    
    def _parse_DSG_indexed_contiguous_compression(self,
                                                  sample_dimension,
                                                  instance_dimension):
        '''

:Parameters:
    
    sample_dimension: `str`
        The netCDF dimension name of the DSG sample dimension.

    element_dimension_1: `str`
        The name of the implied element dimension whose size is the
        maximum number of sub-features in any instance.

    element_dimension_2: `str`
        The name of the implied element dimension whose size is the
        maximum number of elements in any sub-feature.

    '''
        g = self.read_vars
                
        _debug = g['_debug']
        if _debug:
            print 'Pre-processing DSG indexed and contiguous compression'
    
        profile_ncdimension = g['compression'][sample_dimension]['DSG_contiguous']['profile_ncdimension']
    
        if _debug:
            print '    sample_dimension  :', sample_dimension
            print '    instance_dimension:', instance_dimension
            print '    profile_ncdimension :', profile_ncdimension
            
        contiguous = g['compression'][sample_dimension]['DSG_contiguous']
        indexed    = g['compression'][profile_ncdimension]['DSG_indexed']
    
        # The indices of the sample dimension which define the start
        # positions of each instances profiles
        profile_indices = indexed['instances']
    
        profiles_per_instance = indexed['elements_per_instance']
        elements_per_profile  = contiguous['elements_per_instance']
    
        instance_dimension_size  = indexed['instance_dimension_size']
        element_dimension_1_size = int(profiles_per_instance.max())
        element_dimension_2_size = int(elements_per_profile.max())
        
        if _debug:
            print "    Creating g['compression'][{!r}]['DSG_indexed_contiguous']".format(
                sample_dimension)
            
        g['compression'][sample_dimension]['DSG_indexed_contiguous'] = {
            'profiles_per_instance'   : profiles_per_instance,
            'elements_per_profile'    : elements_per_profile,
            'profile_indices'         : profile_indices,
            'implied_ncdimensions'    : (instance_dimension,
                                         indexed['element_dimension'],
                                         contiguous['element_dimension']),
            'instance_dimension_size' : instance_dimension_size,
            'element_dimension_1_size': element_dimension_1_size,
            'element_dimension_2_size': element_dimension_2_size,
        }
    
        if _debug:
            print '    Implied dimensions: {} -> {}'.format(
                sample_dimension,
                g['compression'][sample_dimension]['DSG_indexed_contiguous']['implied_ncdimensions'])
    
        if _debug:
            print "    Removing g['compression'][{!r}]['DSG_contiguous']".format(
                sample_dimension)
            
        del g['compression'][sample_dimension]['DSG_contiguous']
    #--- End: def
    
    def _reference(self, ncvar):
        '''Mark the netCDF variable as being referenced by at least one other
netCDF variable.

:Examples 1:

>>> r._reference('longitude')

:Parameters:

    ncvar: `str`
        The netCDf variable name.

:Returns:

    `None`
        '''
        r = self.read_vars['references'].setdefault(ncvar, 0)
        r += 1
        self.read_vars['references'][ncvar] = r
        return r
    #--- End: def 
    
    def _dereference(self, ncvar):
        '''Mark the netCDF variable as being referenced by at least one other
netCDF variable.

:Examples 1:

>>> r._dereference('longitude')

:Parameters:

    ncvar: `str`
        The netCDf variable name.

:Returns:

    `None`
        '''
        r = self.read_vars['references'].get(ncvar, 0)
        r -= 1
        if r < 0:
            r = 0

        self.read_vars['references'][ncvar] = r
        return r
    #--- End: def 
    
    def _formula_terms_variables(self, field_ncvar, coord_ncvar,
                                 formula_terms, bounds=False,
                                 bounds_ncvar=None):
        '''asdsdsa

:Parameters:
    
    field_ncvar: `str`

    coord_ncvar: `str`
    
    formula_terms: `str`
        A CF-netCDF formula_terms attribute.
    
        '''
        #=============================================================
        # CF-1.7 7.1. Cell Boundaries
        #
        # If a parametric coordinate variable with a formula_terms
        # attribute (section 4.3.2) also has a bounds attribute, its
        # boundary variable must have a formula_terms attribute
        # too. In this case the same terms would appear in both (as
        # specified in Appendix D), since the transformation from the
        # parametric coordinate values to physical space is realized
        # through the same formula.  For any term that depends on the
        # vertical dimension, however, the variable names appearing in
        # the formula terms would differ from those found in the
        # formula_terms attribute of the coordinate variable itself
        # because the boundary variables for formula terms are
        # two-dimensional while the formula terms themselves are
        # one-dimensional.
        #
        # Whenever a formula_terms attribute is attached to a boundary
        # variable, the formula terms may additionally be identified
        # using a second method: variables appearing in the vertical
        # coordinates' formula_terms may be declared to be coordinate,
        # scalar coordinate or auxiliary coordinate variables, and
        # those coordinates may have bounds attributes that identify
        # their boundary variables. In that case, the bounds attribute
        # of a formula terms variable must be consistent with the
        # formula_terms attribute of the boundary variable. Software
        # digesting legacy datasets (constructed prior to version 1.7
        # of this standard) may have to rely in some cases on the
        # first method of identifying the formula term variables and
        # in other cases, on the second. Starting from version 1.7,
        # however, the first method will be sufficient.
        # =============================================================

        g = self.read_vars
        variables = g['nc'].variables
        
        g['formula_terms'].setdefault(coord_ncvar, {'coord' : {},
                                                    'bounds': {}})
        ok = True
        
        parsed_formula_terms = self._parse_x(coord_ncvar, formula_terms)
        cf_compliant = self._check_formula_terms(field_ncvar, coord_ncvar,
                                                 formula_terms,
                                                 parsed_formula_terms)
        if not cf_compliant:
            # There is something wrong with the formula_terms
            # attribut
            return False
        
        for x in parsed_formula_terms:
            term, variable = x.items()[0]
            g['formula_terms'][coord_ncvar]['coord'][term] = variable[0]

        ok = True
        # Bounds formula terms
        if 'bounds' in variables[coord_ncvar].ncattrs():
            bounds_ncvar = variables[coord_ncvar].getncattr('bounds')
            if 'formula_terms' in variables[bounds_ncvar].ncattrs():
                formula_terms = variables[bounds_ncvar].getncattr('formula_terms')
                if formula_terms is not None:
                    parsed_formula_terms = self._parse_x(bounds_ncvar, formula_terms)
                    cf_compliant = self._check_formula_terms(field_ncvar, bounds_ncvar,
                                                             formula_terms,
                                                             parsed_formula_terms)
                    if not cf_compliant:
                        # There is something wrong with the bounds formula_terms
                        # attribute
                        return False
                    
                    for x in parsed_formula_terms:
                        term, variable = x.items()[0]
                        variable = variable[0]
                        g['formula_terms'][coord_ncvar]['bounds'][term] = variable
#                        if z_ncdim in variables[variable].dimensions:
#                            if variable == g['formula_terms'][coord_ncvar]['coord'][term]:
#                                ok = False
#                                self._add_message(
#                                    bounds_ncvar, 0, "oops",
#                                    attribute='formala_terms', value=formula_terms)
#                            # more
#                        elif variable == g['formula_terms'][coord_ncvar]['coord'][term]:
#                            ok = False
#                            self._add_message(
#                                bounds_ncvar, 0, "oops 3",
#                                attribute='formala_terms', value=formula_terms)
#                            
                                
                        
                    if (set(g['formula_terms'][coord_ncvar]['coord']) !=
                        set(g['formula_terms'][coord_ncvar]['bounds'])):
                        ok = False
                        self._add_message(
                            bounds_ncvar, 0, "oops",
                            attribute='formala_terms', value=formula_terms)
                #--- End: if
        #--- End: if

        if not ok:
            return False
        
        return True
    #--- End: def

    def _parse_cell_measures(self, cell_measures):
        '''
        '''
        out = []
        for x in re.findall('\w+:\s+\w+[^\s]', cell_measures):
            out.append(re.split(':\s+', x))

        return out                            
    #--- End: def
    
    def _create_field(self, field_ncvar, attributes, verbose=False):
        '''Create a field for a given netCDF variable.
    
:Parameters:

    field_ncvar: `str`
        The name of the netCDF variable to be turned into a field.

    attributes: `dict`
        Dictionary of the data variable's netCDF attributes.

:Returns:

    out: `Field`
        The new field.

        '''
        g = self.read_vars

        g['read_report'] = {field_ncvar: {}}
        
        nc = g['nc']
        
        _debug = g['_debug']
        if _debug:
            print 'Converting data variable {!r} to a Field:'.format(field_ncvar)
        
        compression = g['compression']
        
        # Add global attributes to the data variable's properties, unless
        # the data variables already has a property with the same name.
        properties = g['global_attributes'].copy()
        properties.update(attributes[field_ncvar])
        
        # Take cell_methods out of the data variable's properties since it
        # will need special processing once the domain has been defined
        cell_methods = properties.pop('cell_methods', None)
        if cell_methods is not None:
            cell_methods = self._CellMethod.parse(cell_methods, allow_error=True)
            error = cell_methods[0].get_error(False)
            if verbose and error:
                print ("WARNING: {0}: {1!r}".format(error, cell_methods[0].get_string('')))
        #--- End: if
    
        # Take add_offset and scale_factor out of the data variable's
        # properties since they will be dealt with by the variable's Data
        # object. Makes sure we note that they were there so we can adjust
        # the field's dtype accordingly
        values = [properties.pop(k, None) for k in ('add_offset', 'scale_factor')]
        unpacked_dtype = (values != [None, None])
        if unpacked_dtype:
            try:
                values.remove(None)
            except ValueError:
                pass
    
            unpacked_dtype = numpy.result_type(*values)
        #--- End: if    
    
        # ----------------------------------------------------------------
        # Initialize the field with the data variable and its attributes
        # ----------------------------------------------------------------
        if _debug:
            print '    Field properties:', properties

        f = self._Field(properties=properties, copy=False)

        # Store the field's netCDF variable name
        self._set_ncvar(f, field_ncvar)
   
        f.set_global_attributes(g['global_attributes'])

        # Map netCDF dimension dimension names to domain axis names.
        # 
        # For example:
        # >>> ncdim_to_axis
        # {'lat': 'dim0', 'time': 'dim1'}
        ncdim_to_axis = {}
    
        ncscalar_to_axis = {}
    
        ncvar_to_key = {}
            
        data_axes = []
    
        # ----------------------------------------------------------------
        # Add axes and non-scalar dimension coordinates to the field
        # ----------------------------------------------------------------
        field_ncdimensions = self._ncdimensions(field_ncvar)
        if _debug:
            print '    Field dimensions:', field_ncdimensions
            
        for ncdim in field_ncdimensions:
            if ncdim in nc.variables and tuple(nc.variables[ncdim].dimensions) == (ncdim,):
                # There is a Unidata coordinate variable for this
                # dimension, so create a domain axis and dimension
                # coordinate
                if ncdim in g['dimension_coordinates']:
                    coord = g['dimension_coordinates'][ncdim].copy()
                else:
                    coord = self._create_bounded_construct(ncdim,
                                                           attributes, f,
                                                           dimension=True,
                                                           verbose=verbose)
                    g['dimension_coordinates'][ncdim] = coord
                
                domain_axis = self._create_domain_axis(coord.get_data().size, ncdim)
                if _debug:
                    print '    [0] Inserting', repr(domain_axis)                    
                axis = self._set_domain_axis(f, domain_axis, copy=False)

                if _debug:
                    print '    [1] Inserting', repr(coord)
                dim = self._set_dimension_coordinate(f, coord,
                                                     axes=[axis], copy=False)
                
                # Set unlimited status of axis
                if nc.dimensions[ncdim].isunlimited():
                    f.unlimited({axis: True})
    
                ncvar_to_key[ncdim] = dim
            else:
                # There is no dimension coordinate for this dimension,
                # so just create a domain axis with the correct size.
                if ncdim in g['new_dimensions']:
                    size = g['new_dimensions'][ncdim]
#                    domain_axis = self._create_domain_axis(size, None)
                else:
                    size = len(nc.dimensions[ncdim])
#                    domain_axis = self._create_domain_axis(size, ncdim)

                domain_axis = self._create_domain_axis(size, ncdim)
                if _debug:
                    print '    [2] Inserting', repr(domain_axis)
                axis = self._set_domain_axis(f, domain_axis, copy=False)
                
                # Set unlimited status of axis
                try:
                    if nc.dimensions[ncdim].isunlimited():
                        f.unlimited({axis: True})
                except KeyError:
                    # This dimension is not in the netCDF file (as might
                    # be the case for an element dimension implied by a
                    # DSG ragged array).
                    pass            
            #--- End: if
    
            # Update data dimension name and set dimension size
            data_axes.append(axis)
    
            ncdim_to_axis[ncdim] = axis
        #--- End: for

        data = self._create_data(field_ncvar, f, unpacked_dtype=unpacked_dtype)        
        if _debug:
            print '    [3] Inserting data from {}: '.format(field_ncvar),
            print '{!r}'.format(data)

        self._set_data(f, data, axes=data_axes, copy=False)
          
        # ----------------------------------------------------------------
        # Add scalar dimension coordinates and auxiliary coordinates to
        # the field
        # ----------------------------------------------------------------
        coordinates = f.del_property('coordinates')
        if coordinates is not None:
            parsed_coordinates = self._parse_y(field_ncvar, coordinates)

            # Split the list (allowing for incorrect comma separated
            # lists).
            for ncvar in parsed_coordinates:
                # Skip dimension coordinates which are in the list
                if ncvar in field_ncdimensions:
                    continue
    
                # Skip auxiliary coordinates which are in the list but not
                # in the file
                if ncvar not in nc.variables:
                    continue
    
                # Set dimensions for this variable 
                dimensions = [ncdim_to_axis[ncdim]
                              for ncdim in self._ncdimensions(ncvar)
                              if ncdim in ncdim_to_axis]
    
                if ncvar in g['auxiliary_coordinates']:
                    coord = g['auxiliary_coordinates'][ncvar].copy()
                else:
                    coord = self._create_bounded_construct(ncvar,
                                                           attributes, f,
                                                           auxiliary=True,
                                                           verbose=verbose)
                    g['auxiliary_coordinates'][ncvar] = coord
                #--- End: if
     
                # --------------------------------------------------------
                # Turn a 
                # --------------------------------------------------------
                is_dimension_coordinate = False
                scalar = False
                if not dimensions:
                    scalar = True
                    if nc.variables[ncvar].dtype.kind is 'S':
                        # String valued scalar coordinate. Is this CF
                        # compliant? Don't worry about it - we'll just
                        # turn it into a 1-d, size 1 auxiliary coordinate
                        # construct.
                        domain_axis = self._create_domain_axis(1)
                        dim = self._set_domain_axis(f, domain_axis)
                        if _debug:
                            print '    [4] Inserting', repr(domain_axis)

                        dimensions = [dim]
                    else:  
                        # Numeric valued scalar coordinate
                        is_dimension_coordinate = True
                #--- End: if
    
                if is_dimension_coordinate:
                    # Insert dimension coordinate
                    coord = self._DimensionCoordinate(source=coord, copy=False)
    
                    if _debug:
                        print '    [5] Inserting', repr(coord)
    
                    domain_axis = self._create_domain_axis(coord.get_data().size)

                    axis = self._set_domain_axis(f, domain_axis, copy=False)
                    
                    dim = self._set_dimension_coordinate(f, coord,
                                                         axes=[axis], copy=False)
                    
                    dimensions = [axis]
                    ncvar_to_key[ncvar] = dim
                    g['dimension_coordinates'][ncvar] = coord
                    del g['auxiliary_coordinates'][ncvar]
                else:
                    # Insert auxiliary coordinate
                    if _debug:
                        print '    [6] Inserting', repr(coord)
                    aux = self._set_auxiliary_coordinate(f, coord,
                                                         axes=dimensions,
                                                         copy=False)
                    ncvar_to_key[ncvar] = aux
                
                if scalar:
                    ncscalar_to_axis[ncvar] = dimensions[0]
            #--- End: for
        #--- End: if
    
        # ----------------------------------------------------------------
        # Add coordinate references from formula_terms properties
        # ----------------------------------------------------------------
        for key, coord in f.coordinates().iteritems():
            coord_ncvar = self._get_ncvar(coord)

            formula_terms = attributes[coord_ncvar].get('formula_terms')        
            if formula_terms is None:
                # This coordinate doesn't have a formula_terms attribute
                continue

            # Get the netCDf dimension name of the vertical dimension
            z_ncdim = nc.variables[coord_ncvar].dimensions[0]

            if coord_ncvar not in g['formula_terms']:                        
                cf_compliant = self._formula_terms_variables(field_ncvar,
                                                             coord_ncvar,
                                                             formula_terms)
                if not cf_compliant:
                    continue
            #--- End: if

            ok = True
            domain_ancillaries = []
            for term, ncvar in g['formula_terms'][coord_ncvar]['coord'].iteritems():
                ncdimensions =  self._ncdimensions(ncvar)
                
                # Set dimensions 
                axes = [ncdim_to_axis[ncdim]
                        for ncdim in ncdimensions
                        if ncdim in ncdim_to_axis]    

                if ncvar in g['domain_ancillaries']:
                    domain_anc = g['domain_ancillaries'][ncvar][1].copy()
                else:
                    bounds = g['formula_terms'][coord_ncvar]['bounds'].get(term)
                    if bounds == ncvar:
                        bounds = None
        
                    domain_anc = self._create_bounded_construct(ncvar,
                                                                attributes,
                                                                f,
                                                                domainancillary=True,
                                                                bounds=bounds,
                                                                verbose=verbose)
                #--- End: if
                
                if len(axes) == len(ncdimensions):
                    domain_ancillaries.append((ncvar, domain_anc, axes))
                else:
                    # The domain ancillary variable spans a dimension
                    # that is not spanned by its parent data variable
                    print '    Not insert coordinate reference'
                    ok = False
                    break
            #--- End: for

            if not ok:
                continue

            # Still here? Create a formula terms coordinate reference.
            for ncvar, domain_anc, axes in domain_ancillaries:
                if _debug:
                    print '    [7] Inserting', repr(domain_anc)
                    
                da_key = self._set_domain_ancillary(f, domain_anc,
                                                    axes=axes, copy=False)
                if ncvar not in ncvar_to_key:
                    ncvar_to_key[ncvar] = da_key
                    
                g['domain_ancillaries'][ncvar] = (da_key, domain_anc)
            #--- End: for
            
            coordinate_reference = self._create_formula_terms_ref(
                f, key, coord,
                g['formula_terms'][coord_ncvar]['coord'])
            self._set_coordinate_reference(f, coordinate_reference, copy=False)
        #--- End: for
    
        # ----------------------------------------------------------------
        # Add grid mapping coordinate references
        # ----------------------------------------------------------------
        grid_mapping = f.del_property('grid_mapping')
        if grid_mapping is not None:
            parsed_grid_mapping = self._parse_x(ncvar, grid_mapping)
            cf_compliant = self._check_grid_mapping(field_ncvar,
                                                    grid_mapping,
                                                    parsed_grid_mapping)
            if not cf_compliant:
                if _debug:
                    print '        Bad grid_mapping:', grid_mapping
            else:              
                coordinate_reference = self._create_grid_mapping_ref(f, grid_mapping,
                                                                     attributes,
                                                                     ncvar_to_key)
                self._set_coordinate_reference(f, coordinate_reference, copy=False)
        #--- End: if
        
        # ----------------------------------------------------------------
        # Add cell measures to the field
        # ----------------------------------------------------------------
        measures = f.del_property('cell_measures')
        if measures is not None:
            parsed_cell_measures = self._parse_x(field_ncvar, measures)
            cf_compliant = self._check_cell_measures(field_ncvar,
                                                     measures,
                                                     parsed_cell_measures)
            if not cf_compliant:
                if _debug:
                    print '    Bad cell_measures:', measures
            else:
                for x in parsed_cell_measures:
                    measure, ncvars = x.items()[0]
                    ncvar = ncvars[0]
                        
                    # Set cell measures' dimensions 
                    cm_ncdimensions = self._ncdimensions(ncvar)
                    axes = [ncdim_to_axis[ncdim] for ncdim in cm_ncdimensions]
        
                    if ncvar in g['cell_measures']:
                        # Copy the cell measure as it already exists
                        cell = g['cell_measures'][ncvar].copy()
                    else:
                        cell = self._create_cell_measure(measure, ncvar,
                                                         attributes)
                        cell.measure = measure
                        g['cell_measures'][ncvar] = cell
                    #--- End: if
        
                    if _debug:
                        print '    [8] Inserting', repr(cell)
                    clm = self._set_cell_measure(f, cell, axes=axes, copy=False)
        
                    ncvar_to_key[ncvar] = clm
            #--- End: if
        #--- End: if
    
        # ----------------------------------------------------------------
        # Add cell methods to the field
        # ----------------------------------------------------------------
        if cell_methods:
            name_to_axis = ncdim_to_axis.copy()
            name_to_axis.update(ncscalar_to_axis)
            for cm in cell_methods:
                cm = cm.change_axes(name_to_axis)
                self._set_cell_method(f, cm, copy=False)
        #--- End: if

        # ----------------------------------------------------------------
        # Add field ancillaries to the field
        # ----------------------------------------------------------------
        ancillary_variables = f.del_property('ancillary_variables')
        if ancillary_variables is not None:
            parsed_ancillary_variables = self._parse_y(field_ncvar, ancillary_variables)
            cf_compliant = self._check_ancillary_variables(field_ncvar,
                                                           ancillary_variables,
                                                           parsed_ancillary_variables)
            if not cf_compliant:
                pass
            else:
                for ncvar in parsed_ancillary_variables:
                    # Set dimensions 
                    anc_ncdimensions = self._ncdimensions(ncvar)
                    axes = [ncdim_to_axis[ncdim] for ncdim in anc_ncdimensions
                            if ncdim in ncdim_to_axis]    
                    
                    if ncvar in g['field_ancillaries']:
                        field_anc = g['field_ancillaries'][ncvar].copy()
                    else:
                        field_anc = self._create_field_ancillary(ncvar, attributes)
                        g['field_ancillaries'][ncvar] = field_anc
                        
                    # Insert the field ancillary
                    if _debug:
                        print '    [9] Inserting', repr(field_anc)                  
                    key = self._set_field_ancillary(f, field_anc, axes=axes, copy=False)
                    ncvar_to_key[ncvar] = key
        #--- End: if

        # Add the structural read report to the field
        f.set_read_report(g.pop('read_report'))
        
        # Return the finished field
        return f
    #--- End: def

    def _add_message(self, ncvar, code, message=None, attribute=None,
                     value=None):
        '''
        '''
        self.read_vars['read_report'].setdefault(ncvar, []).append(
            {'code'     : code,
             'attribute': attribute,
             'value'    : value,
             'message'  : message})
    #--- End: def
    
    def _create_bounded_construct(self, ncvar, attributes, f,
                                  dimension=False, auxiliary=False,
                                  domainancillary=False, bounds=None,
                                  verbose=False):
        '''Create a variable which might have bounds.
    
:Parameters:

    ncvar: `str`
        The netCDF name of the variable.

    attributes: `dict`
        Dictionary of the variable's netCDF attributes.

    f: `Field`
        The parent field.

    dimension: `bool`, optional
        If True then a dimension coordinate is created.

    auxiliary: `bool`, optional
        If True then an auxiliary coordinate is created.

    domainancillary: `bool`, optional
        If True then a domain ancillary is created.

:Returns:

    out : `DimensionCoordinate` or `AuxiliaryCoordinate` or `DomainAncillary`
        The new item.
    
        '''
        g = self.read_vars
        nc = g['nc']
        
        properties = attributes[ncvar].copy()

        properties.pop('formula_terms', None)

        attribute = 'bounds'
        climatology = False
        if bounds is not None:
            ncbounds = bounds
        else:
            ncbounds = properties.pop('bounds', None)
            if ncbounds is None:
                ncbounds = properties.pop('climatology', None)
                if ncbounds is not None:
                    climatology = True
                    attribute = 'climatology'
        #--- End: if
    
        if dimension:
            properties.pop('compress', None) #??
            c = self._DimensionCoordinate(properties=properties)
        elif auxiliary:
            c = self._AuxiliaryCoordinate(properties=properties)
        elif domainancillary:
            properties.pop('coordinates', None)
            properties.pop('grid_mapping', None)
            properties.pop('cell_measures', None)
            properties.pop('positive', None)
            c = self._DomainAncillary(properties=properties)
        else:
            raise ValueError(
"Must set one of the dimension, auxiliary or domainancillary parameters to True")

        if climatology:
            c.set_extent_parameter('climatology', True, copy=False)
    
        data = self._create_data(ncvar, c)
        self._set_data(c, data, copy=False)
        
        # ------------------------------------------------------------
        # Add any bounds
        # ------------------------------------------------------------
        if ncbounds is not None:
                       
            cf_compliant = self._check_bounds(nc, ncvar, attribute, ncbounds)
            if not cf_compliant:
                pass
            else:
                properties = attributes[ncbounds].copy()
                properties.pop('formula_terms', None)                
                bounds = self._Bounds(properties=properties, copy=False)
                    
                bounds_data = self._create_data(ncbounds, bounds)
    
                # Make sure that the bounds dimensions are in the same
                # order as its parent's dimensions. It is assumed that we
                # have already checked that the bounds netCDF variable has
                # appropriate dimensions.
                c_ncdims = nc.variables[ncvar].dimensions
                b_ncdims = nc.variables[ncbounds].dimensions
                c_ndim = len(c_ncdims)
                b_ndim = len(b_ncdims)
                if b_ncdims[:c_ndim] != c_ncdims:
                    axes = [c_ncdims.index(ncdim) for ncdim in b_ncdims[:c_ndim]
                            if ncdim in c_ncdims]
                    axes.extend(range(c_ndim, b_ndim))
                    bounds_data = self._transpose_data(bounds_data,
                                                       axes=axes, copy=False)
                #--- End: if
    
                self._set_data(bounds, bounds_data, copy=False)
                
                # Store the netCDF variable name
                self._set_ncvar(bounds, ncbounds)
    
                self._set_bounds(c, bounds, copy=False)

#                self._reference(ncbounds)
        #--- End: if
    
        # Store the netCDF variable name
        self._set_ncvar(c, ncvar)
   
#        self._reference(ncvar)
                
        # ---------------------------------------------------------
        # Return the bounded variable
        # ---------------------------------------------------------
        return c
    #--- End: def

    
    def _set_auxiliary_coordinate(self, field, construct, axes, copy=True):
        '''Insert a auxiliary coordinate object into a field.

:Parameters:

    field: `Field`

    construct: `AuxiliaryCoordinate`

    axes: `tuple`

    copy: `bool`, optional

:Returns:

    out: `str`
        '''
        self._reference(self._get_ncvar(construct))
        if construct.has_bounds():
            self._reference(self._get_ncvar(construct.get_bounds()))
            
        return field.set_auxiliary_coordinate(construct, axes=axes, copy=copy)
    #--- End: def

    def _set_bounds(self, construct, bounds, copy=True):
        '''
        '''
        construct.set_bounds(bounds, copy=copy)
    #--- End: def
    
    def _set_cell_measure(self, field, construct, axes, copy=True):
        '''Insert a cell_measure object into a field.

:Parameters:

    field: `Field`

    construct: `cell_measure`

    axes: `tuple`

    copy: `bool`, optional

:Returns:

    out: `str`
        '''
        self._reference(self._get_ncvar(construct))

        return field.set_cell_measure(construct, axes=axes, copy=copy)
    #--- End: def
    
    def _set_cell_method(self, field, construct, copy=True):
        '''Insert a cell_method object into a field.

:Parameters:

    field: `Field`

    construct: `cell_method`

    copy: `bool`, optional

:Returns:

    out: `str`
        '''
        return field.set_cell_method(construct, copy=copy)
    #--- End: def

    def _set_coordinate_reference(self, field, construct, copy=True):
        '''Insert a coordinate reference object into a field.

:Parameters:

    field: `Field`

    construct: `CoordinateReference`

    copy: `bool`, optional

:Returns:

    out: `str`
        '''
        ncvar = self._get_ncvar(construct)
        if ncvar is not None:
            self._reference(ncvar)
                    
        return field.set_coordinate_reference(construct, copy=copy)
    #--- End: def

    def _set_dimension_coordinate(self, field, construct, axes, copy=True):
        '''Insert a dimension coordinate object into a field.

:Parameters:

    field: `Field`

    construct: `DimensionCoordinate`

    axes: `tuple`

    copy: `bool`, optional

:Returns:

    out: `str`
        '''
        print '_set_dimension_coordinate:\n',  construct.dump()
        self._reference(self._get_ncvar(construct))
        if construct.has_bounds():
            self._reference(self._get_ncvar(construct.get_bounds()))
            
        return field.set_dimension_coordinate(construct, axes=axes, copy=copy)
    #--- End: def
    
    def _set_domain_ancillary(self, field, construct, axes, copy=True):
        '''Insert a domain ancillary object into a field.

:Parameters:

    field: `Field`

    construct: `DomainAncillary`

    axes: `tuple`

    copy: `bool`, optional

:Returns:

    out: `str`
        '''
        self._reference(self._get_ncvar(construct))
        if construct.has_bounds():
            self._reference(self._get_ncvar(construct.get_bounds()))

        return field.set_domain_ancillary(construct, axes=axes, copy=copy)
    #--- End: def
    
    def _set_domain_axis(self, field, construct, copy=True):
        '''Insert a domain_axis object into a field.

:Parameters:

    field: `Field`

    construct: `domain_axis`

    copy: `bool`, optional

:Returns:

    out: `str`
        '''
        return field.set_domain_axis(construct, copy=copy)
    #--- End: def
    
    def _set_field_ancillary(self, field, construct, axes, copy=True):
        '''Insert a field ancillary object into a field.

:Parameters:

    field: `Field`

    construct: `FieldAncillary`

    axes: `tuple`

    copy: `bool`, optional

:Returns:

    out: `str`
        '''
        self._reference(self._get_ncvar(construct))

        return field.set_field_ancillary(construct, axes=axes, copy=copy)
    #--- End: def
    
    def _set_data(self, construct, data, axes=None, copy=True):
        '''Insert a data object into construct. 

If the construct is a Field then the corresponding domain axes must
also be provided.

:Parameters:

    construct:

    data: `Data`

    axes: `tuple`, optional

    copy: `bool`, optional

:Returns:

    `None`
        '''
        if axes is None:
            construct.set_data(data, copy=copy)
        else:
            construct.set_data(data, axes, copy=copy)
    #--- End: def
    
    def _set_ncvar(self, construct, ncvar):
        '''
        '''
        construct.set_ncvar(ncvar)
    #-- End: def

    def _get_ncvar(self, construct):
       '''
       '''
       return construct.get_ncvar(None)
    #-- End: def

    def _set_ncdim(self, construct, ncdim):
        '''
        '''
        construct.set_ncdim(ncdim)
    #-- End: def

    def _transpose_data(self, data, axes=None, copy=True):
        '''
        '''
        data = data.tranpose(axes=axes, copy=copy)
        return data
    #-- End: def
    
    def _create_cell_measure(self, measure, ncvar, attributes):
        '''Create a cell measure object.
    
:Parameters:

    measure: `str`
        The cell measure.
        
          *Example:*
             ``measure='area'``
    
    ncvar: `str`
        The netCDF name of the cell measure variable.

          *Example:*
             ``ncvar='areacello'``

    attributes: `dict`
        Dictionary of the cell measure variable's netCDF attributes.

:Returns:

    out: `CellMeasure`
        The new item.

        '''
        cell_measure = self._CellMeasure(measure=measure,
                                         properties=attributes[ncvar])
    
        data = self._create_data(ncvar, cell_measure)
    
        self._set_data(cell_measure, data, copy=False)

        # Store the netCDF variable name
        self._set_ncvar(cell_measure, ncvar)
    
#        self._reference(ncvar)

        return cell_measure
    #--- End: def

    def _create_data(self, ncvar, construct=None,
                     unpacked_dtype=False, uncompress_override=None,
                     units=None, calendar=None, fill_value=None):
        '''
    
Set the Data attribute of a variable.

:Parameters:

    ncvar: `str`

    construct: `Variable`, optional

    unpacked_dtype: `False` or `numpy.dtype`, optional

:Returns:

    out: `Data`

:Examples: 
    
    '''
        g = self.read_vars
        nc = g['nc']
        
        ncvariable = nc.variables.get(ncvar)
        if ncvariable is None:
            return None
        
        dtype = ncvariable.dtype
        if unpacked_dtype is not False:
            dtype = numpy.result_type(dtype, unpacked_dtype)
    
        ndim  = ncvariable.ndim
        shape = ncvariable.shape
        size  = ncvariable.size
        if size < 2:
            size = int(size)
    
        if dtype.kind == 'S' and ndim >= 1: #shape[-1] > 1:
            # Has a trailing string-length dimension
            strlen = shape[-1]
            shape = shape[:-1]
            size /= strlen
            ndim -= 1
            dtype = numpy.dtype('S{0}'.format(strlen))
        #--- End: if
    
        filearray = self._NetCDF(filename=g['filename'], ncvar=ncvar,
                                 dtype=dtype, ndim=ndim, shape=shape,
                                 size=size)

        print 'ncvar=',ncvar, 'dtype=',dtype, 'ndim=',ndim, 'shape=',shape, 'size=',size
        # Find the units for the data
        if units is None:
            try:
                units = ncvariable.getncattr('units')
            except AttributeError:
                units = None

        if calendar is None:
            try:
                calendar = ncvariable.getncattr('calendar')
            except AttributeError:
                calendar = None
            
        # Find the fill_value for the data
        if fill_value is None:
            try:
                fill_value = construct.fill_value()
            except AttributeError:
                fill_value = None
                
        compression = g['compression']
    
        if ((uncompress_override is not None and not uncompress_override) or
            not g['compression'] or 
            not g['uncompress'] or
            not set(compression).intersection(ncvariable.dimensions)):        
            # --------------------------------------------------------
            # The array is not compressed
            # --------------------------------------------------------
            data = self._create_Data(filearray, units=units,
                                     calendar=calendar,
                                     fill_value=fill_value)
            
        else:
            # --------------------------------------------------------
            # The array is compressed
            # --------------------------------------------------------
            # Loop round the data variables dimensions as they are in
            # the netCDF file
            for ncdim in ncvariable.dimensions:
                if ncdim in compression:
                    c = compression[ncdim]
                    if 'gathered' in c:
                        data = self._aaa0(ncvar, c['gathered'], filearray, units,
                                          calendar, fill_value)
                    elif 'DSG_indexed_contiguous' in c:
                        # DSG contiguous indexed ragged array. Check
                        # this before DSG_indexed and DSG_contiguous
                        # because both of these will exist for an
                        # indexed and contiguous array.
                        print 'DSG_indexed_contiguous'
                        data = self._aaa3(ncvar,
                                          c['DSG_indexed_contiguous'],
                                          filearray, units, calendar,
                                          fill_value)
                    elif 'DSG_contiguous' in c:                    
                        # DSG contiguous ragged array
                        print 'DSG contiguous ragged array'
                        data = self._aaa1(ncvar, c['DSG_contiguous'],
                                          filearray, units, calendar,
                                          fill_value)
                    elif 'DSG_indexed' in c:
                        # DSG indexed ragged array
                        print 'DSG indexed ragged array'
                        data = self._aaa2(ncvar, c['DSG_indexed'] ,
                                          filearray, units, calendar, fill_value)
                    else:
                        raise ValueError("Bad compression vibes. c.keys()={}".format(c.keys()))
        #--- End: if
                    
        return data
    #--- End: def

    def _create_domain_axis(self, size, ncdim=None):
        '''
        '''
        domain_axis = self._DomainAxis(size)
        if ncdim is not None:
            self._set_ncdim(domain_axis, ncdim)

        return domain_axis
    #-- End: def

    def _create_field_ancillary(self, ncvar, attributes):
        '''Create a field ancillary object.
    
:Parameters:
    
    ncvar: `str`
        The netCDF name of the field ancillary variable.

    attributes: `dict`
        Dictionary of the cell measure variable's netCDF attributes.

:Returns:

    out: `FieldAncillary`
        The new item.

        '''
        field_ancillary = self._FieldAncillary(properties=attributes[ncvar])
    
        data = self._create_data(ncvar, field_ancillary)
    
        self._set_data(field_ancillary, data, copy=False)

        # Store the netCDF variable name
        self._set_ncvar(field_ancillary, ncvar)
    
#        self._reference(ncvar)

        return field_ancillary
    #--- End: def

    def _create_grid_mapping_ref(self, f, grid_mapping,
                                 attributes, ncvar_to_key):
        '''
    
:Parameters:

    f: `Field`

    grid_mapping: `str`
        The value of a CF grid_mapping attribute.

    attributes: `dict`

    ncvar_to_key: `dict`

:Returns:

    `None`

        '''
#        parsed_grid_mapping = self._parse_x(ncvar, grid_mapping)
#        cf_compliant = self._check_grid_mapping(ncvar,
#                                                grid_mapping,
#                                                parsed_grid_mapping)
#        if not cf_compliant:
#            f.del_property('grid_mapping')
#            return
#        
#        for x in parsed_grid_mapping:
#            term, values = x.items()[0]
#`        
        g = self.read_vars
                
        if ':' not in grid_mapping:
            grid_mapping = '{0}:'.format(grid_mapping)

        coordinates = []
        for x in self._parse_grid_mapping(grid_mapping)[::-1]:
            named_coordinates = False
            if not x.endswith(':'):
                try:
                    coordinates.append(ncvar_to_key[x])
                    named_coordinates = True
                except KeyError:
                    continue
            else:
                if not coordinates:
                    coordinates = None
    
                grid_mapping = x[:-1]
    
                if grid_mapping not in attributes:
                    coordinates = []
                    continue
                    
                parameters = attributes[grid_mapping].copy()
                
                props = {}
                name = parameters.pop('grid_mapping_name', None)                 
                if name is not None:
                    props['grid_mapping_name'] = name
                
                if not named_coordinates:
                    coordinates = []
                    for x in self._CoordinateReference._name_to_coordinates.get(name, ()):
                        for key, coord in f.coordinates().iteritems():
                            if x == coord.get_property('standard_name', None):
                                coordinates.append(key)
                #--- End: if
                
                coordref = self._CoordinateReference(properties=props,
                                                     coordinates=coordinates,
                                                     parameters=parameters)

                # Store the netCDF variable name
                self._set_ncvar(coordref, grid_mapping)

#                f.set_coordinate_reference(coordref, copy=False)
    
                coordinates = []
                
#                self._reference(grid_mapping)
        #--- End: for

        return coordref
    #--- End: def
    
    def _create_formula_terms_ref(self, f, key, coord, formula_terms):
        '''
    
:Parameters:

    f: `Field`

    key: `str`

    coord: `Coordinate`

    formula_terms: `dict`
        The formula_terms attribute value from the netCDF file.

    coordref_parameters: `dict`

:Returns:

    out: `CoordinateReference`
    
    '''
        g = self.read_vars

        ancillaries = {}
    
        for term, ncvar in formula_terms.iteritems():
            # The term's value is a domain ancillary of the field, so
            # we put its identifier into the coordinate reference.
            if ncvar in g['domain_ancillaries']:
                ancillaries[term] = g['domain_ancillaries'][ncvar][0]
            else:
                ancillaries[term] = None

        props = {}
        name = coord.get_property('standard_name', None)
        if name is not None:
            props['standard_name'] = name

        coordref = self._CoordinateReference(properties=props,
                                             coordinates=(key,),
                                             domain_ancillaries=ancillaries)
    
#        f.set_coordinate_reference(coordref, copy=False)
    
        return coordref
    #--- End: def

    def _ncdimensions(self, ncvar):
        '''Return a list of the netCDF dimensions corresponding to a netCDF
    variable.
    
:Parameters:

    ncvar: `str`
        The netCDF variable name.

:Returns:

    out: `list`
        The list of netCDF dimension names spanned by the netCDF
        variable.

:Examples: 

>>> _ncdimensions('humidity')
['time', 'lat', 'lon']
    
        '''
        g = self.read_vars
                
        ncvariable = g['nc'].variables[ncvar]
    
        ncattrs = ncvariable.ncattrs()
    
        ncdimensions = list(ncvariable.dimensions)
          
        # Remove a string-length dimension, if there is one. DCH ALERT
        if (ncvariable.dtype.kind == 'S' and
            ncvariable.ndim >= 2 and ncvariable.shape[-1] > 1):
            ncdimensions.pop()
    
        # Check for dimensions which have been compressed. If there are
        # any, then return the netCDF dimensions for the uncompressed
        # variable.
        compression = g['compression']
        if compression and set(compression).intersection(ncdimensions):
            for ncdim in ncdimensions:
                if ncdim in compression:
                    c = compression[ncdim]
                    if 'gathered' in c:
                        # Compression by gathering
                        i = ncdimensions.index(ncdim)
                        ncdimensions[i:i+1] = c['gathered']['implied_ncdimensions']
                    elif 'DSG_indexed_contiguous' in c:
                        # DSG indexed contiguous ragged array.
                        #
                        # Check this before DSG_indexed and DSG_contiguous
                        # because both of these will exist for an array
                        # that is both indexed and contiguous.
                        i = ncdimensions.index(ncdim)
                        ncdimensions = c['DSG_indexed_contiguous']['implied_ncdimensions']
                    elif 'DSG_contiguous' in c:
                        # DSG contiguous ragged array
                        ncdimensions = c['DSG_contiguous']['implied_ncdimensions']
                    elif 'DSG_indexed' in c:
                        # DSG indexed ragged array
                        ncdimensions = c['DSG_indexed']['implied_ncdimensions']
    
                    break
        #--- End: if
        
        return map(str, ncdimensions)
    #--- End: def

    def _parse_grid_mapping(self, grid_mapping):
        '''
        '''
        return re.sub('\s*:\s*', ': ', grid_mapping).split()
    #--- End: def
    
    
    def _aaa0(self, ncvar, c, filearray,  units, calendar, fill_value):
        '''
        '''
        dimensions = self.read_vars['nc'].dimensions
        
        uncompressed_shape = tuple([dimensions[dim].size
                                    for dim in self._ncdimensions(ncvar)])
        uncompressed_ndim  = len(uncompressed_shape)
        uncompressed_size  = long(reduce(operator.mul, uncompressed_shape, 1))
                        
        c = c.copy()
        c['sample_axis'] = g['nc'].variables[ncvar].dimensions.index(ncdim)
        
        xx = self._GatheredArray(
            filearray,
            ndim=uncompressed_ndim,
            shape=uncompressed_shape,
            size=uncompressed_size,
            compression_type=gathered,
            compression_parameters=c
        )
        
        return self._Data(xx, units=units,
                          calendar=calendar,
                          fill_value=fill_value)
    #--- End: def
    
    def _aaa1(self, ncvar, c, filearray, units, calendar, fill_value):
        '''
        '''
        uncompressed_shape = (c['instance_dimension_size'],
                              c['element_dimension_size'])
        uncompressed_ndim  = len(uncompressed_shape)
        uncompressed_size  = long(reduce(operator.mul, uncompressed_shape, 1))

        xx = self._GatheredArray(
            filearray,
            ndim=uncompressed_ndim,
            shape=uncompressed_shape,
            size=uncompressed_size,
            compression_type='DSG_contiguous',
            compression_parameters=c
        )
        
        return self._Data(xx, units=units,
                          calendar=calendar,
                          fill_value=fill_value)
    #--- End: def
    
    def _aaa2(self, ncvar, c, filearray, units, calendar, fill_value):
        '''
        '''
        uncompressed_shape = (c['instance_dimension_size'],
                              c['element_dimension_size'])
        uncompressed_ndim  = len(uncompressed_shape)
        uncompressed_size  = long(reduce(operator.mul, uncompressed_shape, 1))
        
        xx = self._GatheredArray(
            filearray,
            ndim=uncompressed_ndim,
            shape=uncompressed_shape,
            size=uncompressed_size,
            compression_type='DSG_indexed',
            compression_parameters=c
        )
        
        return self._Data(xx, units=units,
                          calendar=calendar,
                          fill_value=fill_value)
    #--- End: def
    
    def _aaa3(self, ncvar, c, filearray, units, calendar, fill_value):
        '''
        '''
        uncompressed_shape = (c['instance_dimension_size'],
                              c['element_dimension_1_size'],
                              c['element_dimension_2_size'])
        uncompressed_ndim  = len(uncompressed_shape)
        uncompressed_size  = long(reduce(operator.mul, uncompressed_shape, 1))
        
        xx = self._GatheredArray(
            filearray,
            ndim=uncompressed_ndim,
            shape=uncompressed_shape,
            size=uncompressed_size,
            compression_type='DSG_indexed_contiguous',
            compression_parameters=c
       )
        
        return self._Data(xx, units=units,
                          calendar=calendar,
                          fill_value=fill_value)
    #--- End: def
    
    def _create_Data(self, array=None, units=None, calendar=None,
                          fill_value=None, netcdf_variable=None):
        '''
        '''
#        try:
#            units = ncvariable.getncattr('units')
#        except AttributeError:
#            units = None
#            
#        try:
#            calendar = ncvariable.getncattr('calendar')
#        except AttributeError:
#            calendar = None
#            
#        # Find the fill_value for the data
#        if fill_value is None:
#            fill_value = construct.fill_value()
            
        return self._Data(array)
    #--- End: def

    # ================================================================
    #
    # Methods for checking CF compliance
    #
    # These methods (whose names all start with "_check") check the
    # minimum required for mapping te file to CFDM structural
    # elements. General CF compliance is not checked (e.g. whether or
    # not grid mapping variable has a grid_mapping_name attribute).
    # ================================================================
    def _check_bounds(self, nc, parent_ncvar, attribute, bounds_ncvar):
        '''asdasdasds

Checks that

  * The bounds variable has exactly one more dimension than the parent
    variable

  * The bounds variable's dimensions, other than the trailing
    dimension are the same, and in the same order, as the parent
    variable's dimensions.

:Parameters:

    nc: `netCDF4.Dataset`
        The netCDF dataset object.

    parent_ncvar: `str`
        The netCDF variable name of the parent variable.

    bounds_ncvar: `str`
        The netCDF variable name of the bounds.

:Returns:

    out: `bool`

        '''
        if bounds_ncvar not in nc.variables:            
            self._add_message(
                parent_ncvar, 0,
                'missing {} variable'.format(attribute),
                attribute=attribute, value=bounds_ncvar)
            return False
        
        c_ncdims = nc.variables[parent_ncvar].dimensions
        b_ncdims = nc.variables[bounds_ncvar].dimensions
        
        if len(b_ncdims) == len(c_ncdims) + 1:
            if c_ncdims != b_ncdims[:-1]:
                self._add_message(
                    bounds_ncvar, 0, 'bad bounds dimensions')
                return False

        elif len(b_ncdims) <= len(c_ncdims) + 1:
            self._add_message(
                bounds_ncvar, 0, 'too few bounds dimensions')
            return False

        elif len(b_ncdims) > len(c_ncdims) + 1:
            self._add_message(
                bounds_ncvar, 0, 'too many bounds dimensions')
            return False

        return True
    #--- End: def
    
    def _check_cell_measures(self, parent_ncvar, string,
                             parsed_string):
        '''
:Parameters:

    nc: `netCDF4.Dataset`
        The netCDF dataset object.

    field_ncvar: `str`
        
    cell_measures: `str`
        The value of the netCDF cell_measures attribute.

    parsed_cell_measures: `list`

:Returns:

    out: `bool`

        '''
        attribute = 'cell_measures'

        nc = self.read_vars['nc']
        
        if not parsed_string:
            self._add_message(
                parent_ncvar, 0,
                'Badly formatted {} attribute'.format(attribute),
                attribute=attribute, value=string)
            return False

        parent_dimensions = set(nc.variables[parent_ncvar].dimensions)
        external_variables = ()
        
        ok = True
        for x in parsed_string:
            measure, values = x.items()[0]
            if len(values) != 1:
                ok = False
                self._add_message(
                    parent_ncvar, 0,
                    'Incorrect {} attribute: {} variables for measure {!r}'.format(attribute, len(values), measure),
                    attribute=attribute, value=string)
                continue

            ncvar = values[0]
            external = (ncvar in external_variables)

            # Check that the variable exists in the file, or if not
            # that it is listed in the 'external_variables' global
            # file attribute
            if ncvar not in nc.variables:
                if not external:
                    ok = False
                    self._add_message(
                        parent_ncvar, 0,
                        'Incorrect {} attribute:  variable {!r} for measure {!r} is not in file nor listed by "external_variables"'.format(attribute, ncvar, measure),
                        attribute=attribute, value=string)
                    continue
                

            # Check that the variable's dimensions span a subset of
            # the parent variable's dimensions. Note that we can only do this if the 
            if (not external and
                not set(nc.variables[ncvar].dimensions).issubset(parent_dimensions)):
                ok = False
                self._add_message(
                    parent_ncvar, 0,
                    'Incorrect {} attribute: variable {!r} spans wrong dimensions'.format(attribute, ncvar),
                    attribute=attribute, value=string)
                continue
        #--- End: for

        return ok
    #--- End: def

    def _check_ancillary_variables(self, parent_ncvar, string,
                                   parsed_string):
        '''
:Parameters:

    field_ncvar: `str`
        
    ancillary_variables: `str`
        The value of the netCDF cell_measures attribute.

    parsed_ancillary_variables: `list`

:Returns:

    out: `bool`

        '''
        attribute = 'ancillary_variables'

        nc = self.read_vars['nc']
        
        if not parsed_string:
            self._add_message(
                parent_ncvar, 0,
                'Incorrectly formatted {} attribute'.format(attribute),
                attribute=attribute, value=string)
            return False

        parent_dimensions = set(nc.variables[parent_ncvar].dimensions)
        
        ok = True
        for ncvar in parsed_string:
            # Check that the variable exists in the file
            if ncvar not in nc.variables:
                ok = False
                self._add_message(
                    parent_ncvar, 0,
                    'Incorrect {} attribute: variable {!r} in file'.format(attribute, ncvar),
                    attribute=attribute, value=string)
                continue
            
            # Check that the variable's dimensions span a subset of
            # the parent variable's dimensions
            if not set(nc.variables[ncvar].dimensions).issubset(parent_dimensions):
                ok = False
                self._add_message(
                    parent_ncvar, 0,
                    'Incorrect {} attribute: variable {!r} spans wrong dimensions'.format(attribute, ncvar),
                    attribute=attribute, value=string)
                continue
        #--- End: for

        return ok
    #--- End: def

    def _check_grid_mapping(self, parent_ncvar, string, parsed_string):
        '''
        '''
        nc = self.read_vars['nc']
        
        if not parsed_string:
            self._add_message(
                parent_ncvar, 0,
                'Badly formed grid_mapping attribute',
                string)
            return False

        ok = True
        for x in parsed_string:
            term, values = x.items()[0]
            if term not in nc.variables:
                ok = False
                self._add_message(
                    parent_ncvar, 0,
                    'missing grid mapping variable',
                    term)
                
            if not values:
                continue
            
            for ncvar in values:
                if ncvar not in nc.variables:
                    ok = False
                    self._add_message(
                        parent_ncvar, 0,
                        'missing grid mapping coordinate variable',
                        ncvar)
                                
        #--- End: for
        
        if not ok:
            return False
        
        return True
    #--- End: def

    def _check_formula_terms(self, field_ncvar, parent_ncvar,
                             formula_terms, parsed_formula_terms):
        '''
        '''

        attribute = 'formula_terms'
        
        nc = self.read_vars['nc']
        
        if not parsed_formula_terms:
            self._add_message(
                parent_ncvar, 0,
                'Incorrectly formatted {} attribute'.format(attribute),
                attribute=attribute, value=formula_terms)
            return False

        ok = True
        for x in parsed_formula_terms:
            term, values = x.items()[0]
            if len(values) != 1:
                ok = False
                self._add_message(
                    parent_ncvar, 0,
                    'Incorrect {} attribute: {} variables for term {!r}'.format(attribute, len(values), term),
                    attribute=attribute, value=formula_terms)
                continue
            
            for ncvar in values:
                if ncvar not in nc.variables:
                    ok = False
                    self._add_message(
                        parent_ncvar, 0,
                        'Incorrect {} attribute: variable {!r} for term {!r} is not in file'.format(attribute, ncvar, term),
                        attribute=attribute, value=formula_terms)
        #--- End: for
        
        if not ok:
            return False
        
        return True
    #--- End: def

    def _check_compress(self, parent_ncvar, compress, parsed_compress):
        '''
        '''
        ncdimensions = self.read_vars['nc'].dimensions

        # Check that each named netCDF dimension exists in the file
        for ncdim in parsed_compress:
            if ncdim not in ncdimensions:
                return False
        #--- End: for
        
        return True
    #--- End: def

    def _check_instance_dimension(self, parent_ncvar, instance_dimension):
        '''asdasd

CF-1.7 Appendix A

* instance_dimension: An attribute which identifies an index variable
                      and names the instance dimension to which it
                      applies. The index variable indicates that the
                      indexed ragged array representation is being
                      used for a collection of features.

        '''        
        # Check that the named netCDF dimension exists in the file
        return instance_dimension in self.read_vars['nc'].dimensions
    #--- End: def
                
    def _check_sample_dimension(self, parent_ncvar, sample_dimension):
        '''asdasd

CF-1.7 Appendix A

* sample_dimension: An attribute which identifies a count variable and
                    names the sample dimension to which it
                    applies. The count variable indicates that the
                    contiguous ragged array representation is being
                    used for a collection of features.

        '''        
        # Check that the named netCDF dimension exists in the file
        return sample_dimension in self.read_vars['nc'].dimensions
    #--- End: def
        
    def _parse_y(self, parent_ncvar, string):
        '''
        '''
        return string.split()
    #--- End: def

    def _parse_x(self, parent_ncvar, string):
        '''

        '''
        # Thanks to Alan Iwi for creating these regexs
        
        def subst(s):
            "substitute tokens for WORD and SEP (space or end of string)"
            return s.replace('WORD', r'[A-Za-z0-9_]+').replace('SEP', r'(\s+|$)')

        out = []
        
        pat_value = subst('(?P<value>WORD)SEP')
        pat_values = '({})+'.format(pat_value)
        
        pat_mapping = subst('(?P<mapping_name>WORD):SEP(?P<values>{})'.format(pat_values))
        pat_mapping_list = '({})+'.format(pat_mapping)
        
        pat_all = subst('((?P<sole_mapping>WORD)|(?P<mapping_list>{}))$'.format(pat_mapping_list))
        
        m = re.match(pat_all, string)

        if m is None:
            return []
            
        sole_mapping = m.group('sole_mapping')
        if sole_mapping:
            out.append({sole_mapping: []})
        else:
            mapping_list = m.group('mapping_list')
            for mapping in re.finditer(pat_mapping, mapping_list):
                term = mapping.group('mapping_name')
                values = [value.group('value')
                          for value in re.finditer(pat_value, mapping.group('values'))]

                out.append({term: values})

        return out
    #--- End: def

#--- End: class

