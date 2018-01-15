import re
import textwrap

from copy      import deepcopy
from cPickle   import dumps, loads, PicklingError
from itertools import izip

import numpy
import netCDF4

from .cfdatetime   import dt
from .functions    import RTOL, ATOL, RELAXED_IDENTITIES
from .functions    import equals     as cf_equals
#from .units        import Units
from .constants    import masked

from .data.data import Data


# ====================================================================
#
# Variable object
#
# ====================================================================

class Variable(object):
    '''

Base class for storing a data array with metadata.

A variable contains a data array and metadata comprising properties to
describe the physical nature of the data.

All components of a variable are optional.

'''
    __metaclass__ = RewriteDocstringMeta

    _special_properties = set(('_FillValue',
                               'missing_value'))

    def __init__(self, properties={}, #attributes=None,
                 data=None,
                 source=None, copy=True):
        '''**Initialization**

:Parameters:

    properties: `dict`, optional
        Initialize properties from the dictionary's key/value pairs.

#    attributes: `dict`, optional
#        Provide attributes from the dictionary's key/value pairs.

    data: `Data`, optional
        Provide a data array.
        
    source: `{+Variable}`, optional
        Take the attributes, CF properties and data array from the
        source {+variable}. Any attributes, CF properties or data
        array specified with other parameters are set after
        initialisation from the source {+variable}.

    copy: `bool`, optional
        If False then do not deep copy arguments prior to
        initialization. By default arguments are deep copied.

        '''
        self._fill_value = None

        self._ncvar = None
        
        # _hasbounds is True if and only if there are cell bounds.
        self._hasbounds = False

        # _hasdata is True if and only if there is a data array
        self._hasdata = False

        # Initialize the _private dictionary, unless it has already
        # been set.
        if not hasattr(self, '_private'):
            self._private = {'special_attributes': {},
                             'properties'        : {}}
        
        if source is not None:
            if not getattr(source, 'isvariable', False):
                raise ValueError(
                    "ERROR: source must be (a subclass of) a Variable: {}".format(
                        source.__class__.__name__))

            if data is None and source.hasdata:
                data = Data.asdata(source)

            p = source.properties()
            if properties:
                p.update(properties)
            properties = p
                
#            a = source.attributes()
#            if attributes:
#                a.update(attributes) 
#            attributes = a
        #--- End: if

        if properties:
            self.properties(properties, copy=copy)

#        self._attribute_names = set()
#        self._attributes = Attributes()
#        if attributes:
#            self.attributes(attributes, copy=copy)

        if data is not None:
            self.insert_data(data, copy=copy)
    #--- End: def

    def __array__(self, *dtype):
        '''

.. versionadded:: 1.6
'''
        if self.hasdata:
            return self.data.__array__(*dtype)

        raise ValueError("Can't initialise numpy array: {} has no data'".format(
            self.__class__.__name__))
    #--- End: def

    def __data__(self):
        '''
Returns a new reference to self.data.

.. versionadded:: 1.6

'''
        if self.hasdata:
            return self.data

        raise ValueError("{} has no data".format(self.__class__.__name__))
    #--- End: def

    def __deepcopy__(self, memo):
        '''

Called by the :py:obj:`copy.deepcopy` standard library function.

.. versionadded:: 1.6

'''
        return self.copy()
    #--- End: def

    def __getitem__(self, indices):
        '''

Called to implement evaluation of x[indices].

x.__getitem__(indices) <==> x[indices]

.. versionadded:: 1.6

'''
        new = self.copy(_omit_data=True)

        if self.hasdata:
            new._Data = self.data[indices]

        return new
    #--- End: def

    def __setitem__(self, indices, value):
        '''

Called to implement assignment to x[indices]

x.__setitem__(indices, value) <==> x[indices]

.. versionadded:: 1.6

'''
        if not self.hasdata:
            raise ValueError("Can't set elements when there is no data")    
            
        if isinstance(value, self.__class__):
            value = value.data

        self.data[indices] = value
    #--- End: def

    def __repr__(self):
        '''
Called by the :py:obj:`repr` built-in function.

x.__repr__() <==> repr(x)

.. versionadded:: 1.6

'''
        return '<{0}: {1}>'.format(self.__class__.__name__, str(self))
    #--- End: def

    def __str__(self):
        '''Called by the :py:obj:`str` built-in function.

x.__str__() <==> str(x)

        '''
        name = self.name('')
        
        if self.hasdata:
            dims = ', '.join([str(x) for x in self.data.shape])
            dims = '({0})'.format(dims)
        else:
            dims = ''

        # Units
        units = self.getprop('units', '')
        if self.isreftime:
            units += ' '+self.getprop('calendar', '')
            
        return '{0}{1} {2}'.format(self.name(''), dims, units)
    #--- End: def

    def _dump_properties(self, omit=(), _level=0):
        '''

.. versionadded:: 1.6

:Parameters:

    omit: sequence of `str`, optional
        Omit the given CF properties from the description.

    _level: `int`, optional

:Returns:

    out: `str`

:Examples:

'''
        indent0 = '    ' * _level

        string = []

        # Simple properties
        simple = self.properties()
        attrs  = sorted(set(simple) - set(omit))
        for attr in attrs:
            name   = '{0}{1} = '.format(indent0, attr)
            value  = repr(simple[attr])
            indent = ' ' * (len(name))
            if value.startswith("'") or value.startswith('"'):
                indent = '%(indent)s ' % locals()

            string.append(textwrap.fill(name+value, 79,
                                        subsequent_indent=indent))
        #--- End: for

        return '\n'.join(string)
    #--- End: def

#    def _simple_properties(self):
#        '''
#
#.. versionadded:: 1.6
#        '''        
#        return self._private['simple_properties']
#    #--- End: def

    def _get_special_attr(self, attr):
        '''

.. versionadded:: 1.6
        
        '''
        d = self._private['special_attributes']
        if attr in d:
            return d[attr]

        raise AttributeError("{} doesn't have attribute {!r}".format(
            self.__class__.__name__, attr))
    #--- End: def
  
    def _set_special_attr(self, attr, value):
        '''

.. versionadded:: 1.6
        '''
        self._private['special_attributes'][attr] = value
    #--- End: def

    def _del_special_attr(self, attr):
        '''

.. versionadded:: 1.6
        '''
        try:
            del self._private['special_attributes']
        except KeyError:
             raise AttributeError("{} doesn't have attribute {!r}".format(
                 self.__class__.__name__, attr))
    #--- End: def

    # ================================================================
    # Attributes
    # ================================================================
    @property
    def _Data(self):
        '''The `Data` object containing the data array.

.. versionadded:: 1.6

        '''
        if self.hasdata:
            return self._private['Data']

        raise AttributeError("{} doesn't have any data".format(
            self.__class__.__name__))
    #--- End: def
    @_Data.setter
    def _Data(self, value):
        private = self._private
        private['Data'] = value

        self._hasdata = True
    #--- End: def
    @_Data.deleter
    def _Data(self):
        private = self._private
        data = private.pop('Data', None)

        if data is None:
            raise AttributeError(
                "Can't delete non-existent data".format(
                    self.__class__.__name__))

        self._hasdata = False
    #--- End: def

    @property
    def data(self):
        '''

The `Data` object containing the data array.

.. versionadded:: 1.6

.. seealso:: `array`, `Data`, `hasdata`, `varray`

:Examples:

>>> if f.hasdata:
...     print f.data

'''       
        if self.hasdata:
            data = self._Data
            data.fill_value = self._fill_value            
            data.units      = self.getprop('units', None)
            data.calendar   = self.getprop('calendar', None)
            return data 

        raise AttributeError("{} object doesn't have attribute 'data'".format(
            self.__class__.__name__))
    #--- End: def
    @data.setter
    def data(self, value):
        old = getattr(self, 'data', None)

        if old is None:
            raise ValueError(
"Can't set 'data' when data has not previously been set with the 'insert_data' method")

        if old.shape != value.shape: 
            raise ValueError(
"Can't set 'data' to new data with different shape. Consider the 'insert_data' method.")
       
        self._Data = value
    #--- End: def
    
    # ----------------------------------------------------------------
    # Attribute (read only)
    # ----------------------------------------------------------------
    @property
    def hasbounds(self):
        '''True if there are cell bounds.

If present then cell bounds are stored in the `!bounds` attribute.

.. versionadded:: 1.6

:Examples:

>>> if c.hasbounds:
...     print c.bounds

        '''      
        return self._hasbounds
    #--- End: def

    # ----------------------------------------------------------------
    # Attribute (read only)
    # ----------------------------------------------------------------
    @property
    def hasdata(self):
        '''

True if there is a data array.

If present, the data array is stored in the `data` attribute.

.. versionadded:: 1.6

.. seealso:: `data`, `hasbounds`

:Examples:

>>> if f.hasdata:
...     print f.data

'''      
        return self._hasdata
    #--- End: def

    def remove_data(self):
        '''Remove and return the data array.

.. versionadded:: 1.6

.. seealso:: `insert_data`

:Returns: 

    out: `Data` or `None`
        The removed data array, or `None` if there isn't one.

:Examples:

>>> f.hasdata
True
>>> print f.data
[0, ..., 9] m
>>> d = f.remove_data()
>>> print d
[0, ..., 9] m
>>> f.hasdata
False
>>> print f.remove_data()
None

        '''
        if not self.hasdata:
            return

        data = self.data
        del self._Data

        return data
    #--- End: def

#    # ----------------------------------------------------------------
#    # CF property
#    # ----------------------------------------------------------------
#    @property
#    def add_offset(self):
#        '''The add_offset CF property.
#
#If present then this number is *subtracted* from the data prior to it
#being written to a file. If both `scale_factor` and `add_offset`
#properties are present, the offset is subtracted before the data are
#scaled. See http://cfconventions.org/latest.html for details.
#
#.. versionadded:: 1.6
#
#:Examples:
#
#>>> f.add_offset = -4.0
#>>> f.add_offset
#-4.0
#>>> del f.add_offset
#
#>>> f.setprop('add_offset', 10.5)
#>>> f.getprop('add_offset')
#10.5
#>>> f.delprop('add_offset')
#
#        '''
#        return self.getprop('add_offset')
#    #--- End: def
#    @add_offset.setter
#    def add_offset(self, value):
#        self.setprop('add_offset', value)
#        self.dtype = numpy.result_type(self.dtype, numpy.array(value).dtype)
#    #--- End: def
#    @add_offset.deleter
#    def add_offset(self):
#        self.delprop('add_offset')
#        if not self.hasprop('scale_factor'):
#            del self.dtype
#    #--- End: def
#
#    # ----------------------------------------------------------------
#    # CF property: calendar
#    # ----------------------------------------------------------------
#    @property
#    def calendar(self):
#        '''The calendar CF property.
#
#The calendar used for encoding time data. See
#http://cfconventions.org/latest.html for details.
#
#.. versionadded:: 1.6
#
#:Examples:
#
#>>> f.calendar = 'noleap'
#>>> f.calendar
#'noleap'
#>>> del f.calendar
#
#>>> f.setprop('calendar', 'proleptic_gregorian')
#>>> f.getprop('calendar')
#'proleptic_gregorian'
#>>> f.delprop('calendar')
#
#        '''
#        return self.getprop('calendar')
#    #--- End: def
#    @calendar.setter
#    def calendar(self, value):
#        self.setprop('calendar', value)
#    @calendar.deleter
#    def calendar(self):
#        self.delprop('calendar')
#
#    # ----------------------------------------------------------------
#    # CF property
#    # ----------------------------------------------------------------
#    @property
#    def comment(self):
#        '''The comment CF property.
#
#Miscellaneous information about the data or methods used to produce
#it. See http://cfconventions.org/latest.html for details.
#
#.. versionadded:: 1.6
#
#:Examples:
#
#>>> f.comment = 'This simulation was done on an HP-35 calculator'
#>>> f.comment
#'This simulation was done on an HP-35 calculator'
#>>> del f.comment
#
#>>> f.setprop('comment', 'a comment')
#>>> f.getprop('comment')
#'a comment'
#>>> f.delprop('comment')
#
#        '''
#        return self.getprop('comment')
#    #--- End: def
#    @comment.setter
#    def comment(self, value):
#        self.setprop('comment', value)
#    @comment.deleter
#    def comment(self):
#        self.delprop('comment')

    # ----------------------------------------------------------------
    # CF property
    # ----------------------------------------------------------------
    @property
    def _FillValue(self):
        '''The _FillValue CF property.

A value used to represent missing or undefined data.

Note that this property is primarily for writing data to disk and is
independent of the missing data mask. It may, however, get used when
unmasking data array elements. See
http://cfconventions.org/latest.html for details.

The recommended way of retrieving the missing data value is with the
`fill_value` method.

.. versionadded:: 1.6

.. seealso:: `fill_value`, `missing_value`

:Examples:

>>> f._FillValue = -1.0e30
>>> f._FillValue
-1e+30
>>> del f._FillValue

        '''
        d = self._private['properties']
        if '_FillValue' in d:
            return d['_FillValue']

        raise AttributeError("%s doesn't have CF property '_FillValue'" %
                             self.__class__.__name__)
    #--- End: def

    @_FillValue.setter
    def _FillValue(self, value):
#        self.setprop('_FillValue', value) 
        self._private['properties']['_FillValue'] = value
        self._fill_value = self.getprop('missing_value', value)
    #--- End: def

    @_FillValue.deleter
    def _FillValue(self):
        self._private['properties'].pop('_FillValue', None)
        self._fill_value = getattr(self, 'missing_value', None)
    #--- End: def

#    # ----------------------------------------------------------------
#    # CF property
#    # ----------------------------------------------------------------
#    @property
#    def history(self):
#        '''The history CF property.
#
#A list of the applications that have modified the original data. See
#http://cfconventions.org/latest.html for details.
#
#.. versionadded:: 1.6
#
#:Examples:
#
#>>> f.history = 'created on 2012/10/01'
#>>> f.history
#'created on 2012/10/01'
#>>> del f.history
#
#>>> f.setprop('history', 'created on 2012/10/01')
#>>> f.getprop('history')
#'created on 2012/10/01'
#>>> f.delprop('history')
#
#        '''
#        return self.getprop('history')
#    #--- End: def
#
#    @history.setter
#    def history(self, value): self.setprop('history', value)
#    @history.deleter
#    def history(self):        self.delprop('history')
#
#    # ----------------------------------------------------------------
#    # CF property
#    # ----------------------------------------------------------------
#    @property
#    def leap_month(self):
#        '''The leap_month CF property.
#
#Specifies which month is lengthened by a day in leap years for a user
#defined calendar. See http://cfconventions.org/latest.html for
#details.
#
#.. versionadded:: 1.6
#
#:Examples:
#
#>>> f.leap_month = 2
#>>> f.leap_month
#2
#>>> del f.leap_month
#
#>>> f.setprop('leap_month', 11)
#>>> f.getprop('leap_month')
#11
#>>> f.delprop('leap_month')
#
#        '''
#        return self.getprop('leap_month')
#    #--- End: def
#    @leap_month.setter
#    def leap_month(self, value): self.setprop('leap_month', value)
#    @leap_month.deleter
#    def leap_month(self):        self.delprop('leap_month')
#
#    # ----------------------------------------------------------------
#    # CF property
#    # ----------------------------------------------------------------
#    @property
#    def leap_year(self):
#        '''The leap_year CF property.
#
#Provides an example of a leap year for a user defined calendar. It is
#assumed that all years that differ from this year by a multiple of
#four are also leap years. See http://cfconventions.org/latest.html for
#details.
#
#.. versionadded:: 1.6
#
#:Examples:
#
#>>> f.leap_year = 1984
#>>> f.leap_year
#1984
#>>> del f.leap_year
#
#>>> f.setprop('leap_year', 1984)
#>>> f.getprop('leap_year')
#1984
#>>> f.delprop('leap_year')
#
#        '''
#        return self.getprop('leap_year')
#    #--- End: def
#    @leap_year.setter
#    def leap_year(self, value): self.setprop('leap_year', value)
#    @leap_year.deleter
#    def leap_year(self):        self.delprop('leap_year')
#
#    # ----------------------------------------------------------------
#    # CF property
#    # ----------------------------------------------------------------
#    @property
#    def long_name(self):
#        '''The long_name CF property.
#
#A descriptive name that indicates a nature of the data. This name is
#not standardized. See http://cfconventions.org/latest.html for
#details.
#
#.. versionadded:: 1.6
#
#:Examples:
#
#>>> f.long_name = 'zonal_wind'
#>>> f.long_name
#'zonal_wind'
#>>> del f.long_name
#
#>>> f.setprop('long_name', 'surface air temperature')
#>>> f.getprop('long_name')
#'surface air temperature'
#>>> f.delprop('long_name')
#
#        '''
#        return self.getprop('long_name')
#    #--- End: def
#    @long_name.setter
#    def long_name(self, value): self.setprop('long_name', value)
#    @long_name.deleter
#    def long_name(self):        self.delprop('long_name')

    # ----------------------------------------------------------------
    # CF property
    # ----------------------------------------------------------------
    @property
    def missing_value(self):
        '''The missing_value CF property.

A value used to represent missing or undefined data (deprecated by the
netCDF user guide). See http://cfconventions.org/latest.html for
details.

Note that this attribute is used primarily for writing data to disk
and is independent of the missing data mask. It may, however, be used
when unmasking data array elements.

The recommended way of retrieving the missing data value is with the
`fill_value` method.

.. versionadded:: 1.6

.. seealso:: `_FillValue`, `fill_value`

:Examples:

>>> f.missing_value = 1.0e30
>>> f.missing_value
1e+30
>>> del f.missing_value
        '''        
        d = self._private['properties']
        if 'missing_value' in d:
            return d['missing_value']

        raise AttributeError("%s doesn't have CF property 'missing_value'" %
                             self.__class__.__name__)
     #--- End: def
    @missing_value.setter
    def missing_value(self, value):
        self._private['properties']['missing_value'] = value
        self._fill_value = value
    #--- End: def
    @missing_value.deleter
    def missing_value(self):
        self._private['properties'].pop('missing_value', None)
        self._fill_value = getattr(self, '_FillValue', None)
    #--- End: def

#    # ----------------------------------------------------------------
#    # CF property
#    # ----------------------------------------------------------------
#    @property
#    def month_lengths(self):
#        '''The month_lengths CF property.
#
#Specifies the length of each month in a non-leap year for a user
#defined calendar. See http://cfconventions.org/latest.html for
#details.
#
#Stored as a tuple but may be set as any array-like object.
#
#.. versionadded:: 1.6
#
#:Examples:
#
#>>> f.month_lengths = numpy.array([34, 31, 32, 30, 29, 27, 28, 28, 28, 32, 32, 34])
#>>> f.month_lengths
#(34, 31, 32, 30, 29, 27, 28, 28, 28, 32, 32, 34)
#>>> del f.month_lengths
#
#>>> f.setprop('month_lengths', [34, 31, 32, 30, 29, 27, 28, 28, 28, 32, 32, 34])
#>>> f.getprop('month_lengths')
#(34, 31, 32, 30, 29, 27, 28, 28, 28, 32, 32, 34)
#>>> f.delprop('month_lengths')
#
#        '''
#        return self.getprop('month_lengths')
#    #--- End: def
#
#    @month_lengths.setter
#    def month_lengths(self, value): self.setprop('month_lengths', tuple(value))
#    @month_lengths.deleter
#    def month_lengths(self):        self.delprop('month_lengths')
#
#    # ----------------------------------------------------------------
#    # CF property
#    # ----------------------------------------------------------------
#    @property
#    def scale_factor(self):
#        '''The scale_factor CF property.
#
#If present then the data are *divided* by this factor prior to it
#being written to a file. If both `scale_factor` and `add_offset`
#properties are present, the offset is subtracted before the data are
#scaled. See http://cfconventions.org/latest.html for details.
#
#.. versionadded:: 1.6
#
#:Examples:
#
#>>> f.scale_factor = 10.0
#>>> f.scale_factor
#10.0
#>>> del f.scale_factor
#
#>>> f.setprop('scale_factor', 10.0)
#>>> f.getprop('scale_factor')
#10.0
#>>> f.delprop('scale_factor')
#
#        '''
#        return self.getprop('scale_factor')
#    #--- End: def
#    @scale_factor.setter
#    def scale_factor(self, value): self.setprop('scale_factor', value)
#    @scale_factor.deleter
#    def scale_factor(self):        self.delprop('scale_factor')
#
#    # ----------------------------------------------------------------
#    # CF property
#    # ----------------------------------------------------------------
#    @property
#    def standard_name(self):
#        '''The standard_name CF property.
#
#A standard name that references a description of a data in the
#standard name table
#(http://cfconventions.org/standard-names.html). See
#http://cfconventions.org/latest.html for details.
#
#.. versionadded:: 1.6
#
#:Examples:
#
#>>> f.standard_name = 'time'
#>>> f.standard_name
#'time'
#>>> del f.standard_name
#
#>>> f.setprop('standard_name', 'time')
#>>> f.getprop('standard_name')
#'time'
#>>> f.delprop('standard_name')
#
#        '''
#        return self.getprop('standard_name')
#    #--- End: def
#    @standard_name.setter
#    def standard_name(self, value):
#        self.setprop('standard_name', value)
#    @standard_name.deleter
#    def standard_name(self):
#        self.delprop('standard_name')
#
#    # ----------------------------------------------------------------
#    # CF property
#    # ----------------------------------------------------------------
#    @property
#    def units(self):
#        '''The units CF property.
#
#The units of the data. The value of the `units` property is a string
#that can be recognized by UNIDATA's Udunits package
#(http://www.unidata.ucar.edu/software/udunits). See
#http://cfconventions.org/latest.html for details.
#
#.. versionadded:: 1.6
#
#:Examples:
#
#>>> f.units = 'K'
#>>> f.units
#'K'
#>>> del f.units
#
#>>> f.setprop('units', 'm.s-1')
#>>> f.getprop('units')
#'m.s-1'
#>>> f.delprop('units')
#
#        '''
#        return self.getprop('units')
#    #--- End: def
#    @units.setter
#    def units(self, value):
#        self.setprop('units', value)
#    @units.deleter
#    def units(self):
#        self.delprop('units')
#
#    # ----------------------------------------------------------------
#    # CF property
#    # ----------------------------------------------------------------
#    @property
#    def valid_max(self):
#        '''The valid_max CF property.
#
#The largest valid value of the data. See
#http://cfconventions.org/latest.html for details.
#
#.. versionadded:: 1.6
#
#:Examples:
#
#>>> f.valid_max = 100.0
#>>> f.valid_max
#100.0
#>>> del f.valid_max
#
#>>> f.setprop('valid_max', 100.0)
#>>> f.getprop('valid_max')
#100.0
#>>> f.delprop('valid_max')
#
#        '''
#        return self.getprop('valid_max')
#    #--- End: def
#    @valid_max.setter
#    def valid_max(self, value):
#        self.setprop('valid_max', value)
#    @valid_max.deleter
#    def valid_max(self):
#        self.delprop('valid_max')
#
#    # ----------------------------------------------------------------
#    # CF property
#    # ----------------------------------------------------------------
#    @property
#    def valid_min(self):
#        '''The valid_min CF property.	
#
#The smallest valid value of the data. See
#http://cfconventions.org/latest.html for details.
#
#.. versionadded:: 1.6
#
#:Examples:
#
#>>> f.valid_min = 8.0
#>>> f.valid_min
#8.0
#>>> del f.valid_min
#
#>>> f.setprop('valid_min', 8.0)
#>>> f.getprop('valid_min')
#8.0
#>>> f.delprop('valid_min')
#
#        '''
#        return self.getprop('valid_min')
#    #--- End: def
#    @valid_min.setter
#    def valid_min(self, value): self.setprop('valid_min', value)
#    @valid_min.deleter
#    def valid_min(self):        self.delprop('valid_min')
#
#    # ----------------------------------------------------------------
#    # CF property
#    # ----------------------------------------------------------------
#    @property
#    def valid_range(self):
#        '''The valid_range CF property.
#
#The smallest and largest valid values the data. See
#http://cfconventions.org/latest.html for details.
#
#Stored as a tuple but may be set as any array-like object.
#
#.. versionadded:: 1.6
#
#:Examples:
#
#>>> f.valid_range = numpy.array([100., 400.])
#>>> f.valid_range
#(100.0, 400.0)
#>>> del f.valid_range
#
#>>> f.setprop('valid_range', [100.0, 400.0])
#>>> f.getprop('valid_range')
#(100.0, 400.0)
#>>> f.delprop('valid_range')
#
#        '''
#        return tuple(self.getprop('valid_range'))
#    #--- End: def
#    @valid_range.setter
#    def valid_range(self, value): self.setprop('valid_range', tuple(value))
#    @valid_range.deleter
#    def valid_range(self):        self.delprop('valid_range')
#
#    # ----------------------------------------------------------------
#    # Attribute (read only)
#    # ----------------------------------------------------------------
#    @property
#    def shape(self):
#        '''
#
#A tuple of the data array's dimension sizes.
#
#.. versionadded:: 1.6
#
#.. seealso:: `data`, `hasdata`, `ndim`, `size`
#
#:Examples:
#
#>>> f.shape
#(73, 96)
#>>> f.ndim
#2
#
#>>> f.ndim
#0
#>>> f.shape
#()
#
#>>> f.hasdata
#True
#>>> len(f.shape) == f.dnim
#True
#>>> reduce(lambda x, y: x*y, f.shape, 1) == f.size
#True
#
#'''
#        if self.hasdata:
#            return self.data.shape
#
#        raise AttributeError(
#            "{} doesn't have attribute 'shape' (there is no data)".format(
#                self.__class__.__name__))
#    #--- End: def

#    # ----------------------------------------------------------------
#    # Attribute (read only)
#    # ----------------------------------------------------------------
#    @property
#    def ndim(self):
#        '''
#
#The number of dimensions in the data array.
#
#.. versionadded:: 1.6
#
#.. seealso:: `data`, `hasdata`, `shape`
#
#:Examples:
#
#>>> f.hasdata
#True
#>>> f.shape
#(73, 96)
#>>> f.ndim
#2
#
#>>> f.shape
#()
#>>> f.ndim
#0
#
#'''
#        if self.hasdata:
#            return self.data.ndim
#
#        raise AttributeError(
#            "{} doesn't have attribute 'ndim' (there is no data)".format(
#                self.__class__.__name__))
#    #--- End: def
#
#    # ----------------------------------------------------------------
#    # Attribute (read only)
#    # ----------------------------------------------------------------
#    @property
#    def size(self):
#        '''
#The number of elements in the data array.
#
#.. versionadded:: 1.6
#
#.. seealso:: `data`, `hasdata`, `ndim`, `shape`
#
#:Examples:
#
#>>> f.shape
#(73, 96)
#>>> f.size
#7008
#
#>>> f.shape
#()
#>>> f.ndim
#0
#>>> f.size
#1
#
#>>> f.shape
#(1, 1, 1)
#>>> f.ndim
#3
#>>> f.size
#1
#
#s>>> f.hasdata
#True
#>>> f.size == reduce(lambda x, y: x*y, f.shape, 1)
#True
#
#'''
#        if self.hasdata:
#            return self.data.size
#        
#        raise AttributeError(
#            "{} doesn't have attribute 'size' (there is no data)".format(
#                self.__class__.__name__))
#    #--- End: def

    # ----------------------------------------------------------------
    # Attribute (read only)
    # ----------------------------------------------------------------
    @property
    def dtarray(self):
        '''An independent numpy array of date-time objects.

Only applicable for reference time units.

If the calendar has not been set then the CF default calendar will be
used.

The data type of the data array is unchanged.

.. versionadded:: 1.6

.. seealso:: `array`, `asdatetime`, `asreftime`, `dtvarray`, `varray`

:Examples:

        '''
        if not self.hasdata:
            raise AttributeError("{} has no data".format(self.__class__.__name__))

        return self.data.dtarray
#
#        array = self.data.array
#
#        mask = None
#        if numpy.ma.isMA(array):
#            # num2date has issues if the mask is nomask
#            mask = array.mask
#            if mask is numpy.ma.nomask or not numpy.ma.is_masked(array):
#                array = array.view(numpy.ndarray)
#        #--- End: if
#
#        utime = Utime(self.getprop('units'),
#                      self.getptop('calendar', 'gregorian'))
#        array = utime.num2date(array)
#    
#        if mask is None:
#            # There is no missing data
#            array = numpy.array(array, dtype=object)
#        else:
#            # There is missing data
#            array = numpy.ma.masked_where(mask, array)
#            if not numpy.ndim(array):
#                array = numpy.ma.masked_all((), dtype=object)
#
#        return array
#    #--- End: def
#
#    # ----------------------------------------------------------------
#    # Attribute
#    # ----------------------------------------------------------------
#    @property
#    def dtype(self):
#        '''The `numpy` data type of the data array.
#
#Setting the data type to a `numpy.dtype` object (or any object
#convertible to a `numpy.dtype` objec, such as the string ``'int32'``),
#will cause the data array elements to be recast to the specified type.
#
#.. versionadded:: 1.6
#
#:Examples:
#
#>>> f.dtype
#dtype('float64')
#>>> type(f.dtype)
#<type 'numpy.dtype'>
#
#>>> print f.array
#[0.5 1.5 2.5]
#>>> import numpy
#>>> f.dtype = numpy.dtype(int)
#>>> print f.array
#[0 1 2]
#>>> f.dtype = bool
#>>> print f.array
#[False  True  True]
#>>> f.dtype = 'float64'
#>>> print f.array
#[ 0.  1.  1.]
#
#        '''
#        if self.hasdata:
#            return self.data.dtype
#
#        raise AttributeError(
#            "Can't get {} 'dtype' when there is no data".format(
#                self.__class__.__name__))
#    #--- End: def
#    @dtype.setter
#    def dtype(self, value):
#        if self.hasdata:
#            self.data.dtype = value
#        else:
#            raise AttributeError(
#                "Can't set {} 'dtype' when there is no data".format(
#                    self.__class__.__name__))

#    # ----------------------------------------------------------------
#    # Attribute (read only)
#    # ----------------------------------------------------------------
#    @property
#    def array(self):
#        '''An independent numpy array copy of the data.
#
#.. versionadded:: 1.6
#
#.. seealso:: `data`, `dtarray`, `varray`
#
#:Examples 1:
#
#>>> print f.data
#[0, ... 4] kg m-1 s-2
#>>> a = f.array
#>>> type(a)
#<type 'numpy.ndarray'>
#>>> print a
#[0 1 2 3 4]
#>>> a[0] = 999
#>>> print a
#[999 1 2 3 4]
#>>> print f.array
#[0 1 2 3 4]
#>>> print f.data
#[0, ... 4] kg m-1 s-2
#
#        '''
#        if self.hasdata:
#            return self.data.array
#
#        raise AttributeError(
#            "{} has no data array".format(self.__class__.__name__))
#    #--- End: def
#
#    # ----------------------------------------------------------------
#    # Attribute (read only)
#    # ----------------------------------------------------------------
#    @property
#    def varray(self):
#        '''A numpy array view of the data array.
#
#Changing the elements of the returned view changes the data array.
#
#.. versionadded:: 1.6
#
#.. seealso:: `array`, `data`, `dtarray`
#
#:Examples 1:
#
#>>> f.data
#<Data: [0, ..., 4] kg m-1 s-2>
#>>> a = f.array
#>>> type(a)
#<type 'numpy.ndarray'>
#>>> print a
#[0 1 2 3 4]
#>>> a[0] = 999
#>>> print a
#[999 1 2 3 4]
#>>> print f.array
#[999 1 2 3 4]
#>>> f.data
#<Data: [999, ..., 4] kg m-1 s-2>
#
#        '''
#        if self.hasdata:
#            return self.data.varray
#
#        raise AttributeError("{} has no data array".format(
#            self.__class__.__name__))
#    #--- End: def
#
#    def close(self):
#        '''
#'''
#        if self.hasdata:
#            self.data.close()
#    #--- End: def

    def copy(self, _omit_data=False, _only_data=False,
             _omit_special=None, _omit_properties=False,
             _omit_attributes=False):
        '''Return a deep copy.

``f.copy()`` is equivalent to ``copy.deepcopy(f)``.

.. versionadded:: 1.6

:Examples 1:

>>> g = f.copy()

:Returns:

    out: `{+Variable}`
        The deep copy.

:Examples 2:

>>> g = f.copy()
>>> g is f
False
>>> f.equals(g)
True
>>> import copy
>>> h = copy.deepcopy(f)
>>> h is f
False
>>> f.equals(g)
True

        '''
        new = type(self)()
#        ts = type(self)
#        new = ts.__new__(ts)

        if _only_data:
            if self.hasdata:
                new._Data = self.data.copy()

            return new
        #--- End: if

        self_dict = self.__dict__.copy()
        
        self_private = self_dict.pop('_private')
            
        del self_dict['_hasdata']
        new.__dict__['_fill_value'] = self_dict.pop('_fill_value')
        new.__dict__['_hasbounds']  = self_dict.pop('_hasbounds')
            
        if self_dict and not _omit_attributes:        
            try:
                new.__dict__.update(loads(dumps(self_dict, -1)))
            except PicklingError:
                new.__dict__.update(deepcopy(self_dict))
                
        private = {}

        if not _omit_data and self.hasdata:
            private['Data'] = self_private['Data'].copy()
            new._hasdata = True
 
        # ------------------------------------------------------------
        # Copy special attributes. These attributes are special
        # because they have a copy() method which return a deep copy.
        # ------------------------------------------------------------
        special = self_private['special_attributes'].copy()
        if _omit_special:            
            for prop in _omit_special:
                special.pop(prop, None)

        for prop, value in special.iteritems():
            special[prop] = value.copy()

        private['special_attributes'] = special

        if not _omit_properties:
            try:
                private['properties'] = loads(dumps(self_private['properties'], -1))
            except PicklingError:
                private['properties'] = deepcopy(self_private['properties'])
        else:
            private['properties'] = {}

        new._private = private

        if self.hasbounds:
            bounds = self.bounds.copy(_omit_data=_omit_data,
                                      _only_data=_only_data)
            new._set_special_attr('bounds', bounds)        

        return new
    #--- End: def

    def datum(self, *index):
        '''

Return an element of the data array as a standard Python scalar.

The first and last elements are always returned with ``f.datum(0)``
and ``f.datum(-1)`` respectively, even if the data array is a scalar
array or has two or more dimensions.

.. versionadded:: 1.6

.. seealso:: `array`

:Parameters:

    index: optional
        Specify which element to return. When no positional arguments
        are provided, the method only works for data arrays with one
        element (but any number of dimensions), and the single element
        is returned. If positional arguments are given then they must
        be one of the following:

          * An integer. This argument is interpreted as a flat index
            into the array, specifying which element to copy and
            return.
         
              Example: If the data aray shape is ``(2, 3, 6)`` then:
                * ``f.{+name}(0)`` is equivalent to ``f.{+name}(0, 0, 0)``.
                * ``f.{+name}(-1)`` is equivalent to ``f.{+name}(1, 2, 5)``.
                * ``f.{+name}(16)`` is equivalent to ``f.{+name}(0, 2, 4)``.

            If *index* is ``0`` or ``-1`` then the first or last data
            array element respecitively will be returned, even if the
            data array is a scalar array or has two or more
            dimensions.
        ..
         
          * Two or more integers. These arguments are interpreted as a
            multidimensionsal index to the array. There must be the
            same number of integers as data array dimensions.
        ..
         
          * A tuple of integers. This argument is interpreted as a
            multidimensionsal index to the array. There must be the
            same number of integers as data array dimensions.
         
              Example: ``f.datum((0, 2, 4))`` is equivalent to
              ``f.datum(0, 2, 4)``; and ``f.datum(())`` is equivalent
              to ``f.datum()``.

:Returns:

    out:
        A copy of the specified element of the array as a suitable
        Python scalar.

:Examples:

>>> print f.array
2
>>> f.{+name}()
2
>>> 2 == f.{+name}(0) == f.{+name}(-1) == f.{+name}(())
True

>>> print f.array
[[2]]
>>> 2 == f.{+name}() == f.{+name}(0) == f.{+name}(-1)
True
>>> 2 == f.{+name}(0, 0) == f.{+name}((-1, -1)) == f.{+name}(-1, 0)
True

>>> print f.array
[[4 -- 6]
 [1 2 3]]
>>> f.{+name}(0)
4     
>>> f.{+name}(-1)
3     
>>> f.{+name}(1)
masked
>>> f.{+name}(4)
2     
>>> f.{+name}(-2)
2     
>>> f.{+name}(0, 0)
4     
>>> f.{+name}(-2, -1)
6     
>>> f.{+name}(1, 2)
3     
>>> f.{+name}((0, 2))
6

'''
        if not self.hasdata:
            raise ValueError(
                "ERROR: Can't return an element when there is no data array")
        
        return self.data.datum(*index)
    #--- End: def

    def dump(self, display=True, prefix=None, omit=(), field=None,
             key=None, _title=None, _level=0):
        '''

Return a string containing a full description of the instance.

.. versionadded:: 1.6

:Parameters:

    display: `bool`, optional
        If False then return the description as a string. By default
        the description is printed, i.e. ``f.dump()`` is equivalent to
        ``print f.dump(display=False)``.

    omit: sequence of `str`, optional
        Omit the given CF properties from the description.

    prefix: optional
        Ignored.

:Returns:

    out: `None` or `str`
        A string containing the description.

:Examples:

>>> f.{+name}()
Data(1, 2) = [[2999-12-01 00:00:00, 3000-12-01 00:00:00]] 360_day
axis = 'T'
standard_name = 'time'

>>> f.{+name}(omit=('axis',))
Data(1, 2) = [[2999-12-01 00:00:00, 3000-12-01 00:00:00]] 360_day
standard_name = 'time'

'''
        indent0 = '    ' * _level
        indent1 = '    ' * (_level+1)

        if _title is None:
            string = ['{0}Variable: {1}{2})'.format(indent0,
                                                    self.name(default=''))]
        else:
            string = [indent0 + _title]
                        
        _properties = self._dump_properties(omit=omit, _level=_level+1)
        if _properties:
            string.append(_properties)

        if self.hasdata:
            if field and key:
                x = ['{0}({1})'.format(field.domain_axis_name(axis),
                                       field.domain_axes()[axis].size)
                     for axis in field.construct_axes(key)]
            else:
                x = [str(s) for s in self.data.shape]

            data = self.data
            if self.isreftime:
                data = data.asdata(self.dtarray)
           
            string.append('{0}Data({1}) = {2}'.format(indent1,
                                                      ', '.join(x),
                                                      str(data)))
        #--- End: if
        
        string = '\n'.join(string)
       
        if display:
            print string
        else:
            return string
    #--- End: def

    def _parse_axes(self, axes):
        if axes is None:
            return axes

        ndim = self.data.ndim
        return [(i + ndim if i < 0 else i) for i in axes]
    #--- End: def
    
#    @property
#    def mask(self):
#        '''The mask of the data array.
#
#Values of True indicate masked elements.
#
#.. versionadded:: 1.6
#
#.. seealso:: `binary_mask`
#
#:Examples:
#
#>>> f.shape
#(12, 73, 96)
#>>> m = f.mask
#>>> m.long_name
#'mask'
#>>> m.shape
#(12, 73, 96)
#>>> m.dtype
#dtype('bool')
#>>> print m.data
#[[[True, ..., False]]]
#
#        '''
#        if not self.hasdata:
#            raise ValueError(
#                "ERROR: Can't get mask when there is no data array")
#
#        out = self.copy(_omit_data=True, _omit_properties=True,
#                        _omit_attributes=True)
#
#        out.insert_data(self.data.mask, copy=False)            
#        out.long_name = 'mask'
#
#        return out
#    #--- End: def


    def equals(self, other, rtol=None, atol=None,
               ignore_data_type=False, ignore_fill_value=False,
               traceback=False, ignore=(), ignore_type=False, **kwargs):
        '''

True if two {+variable}s are equal, False otherwise.

.. versionadded:: 1.6

:Parameters:

    other: 
        The object to compare for equality.

    {+atol}

    {+rtol}

    ignore_fill_value: `bool`, optional
        If True then data arrays with different fill values are
        considered equal. By default they are considered unequal.

    traceback: `bool`, optional
        If True then print a traceback highlighting where the two
        {+variable}s differ.

    ignore: `tuple`, optional
        The names of CF properties to omit from the comparison.

:Returns: 

    out: `bool`
        Whether or not the two {+variable}s are equal.

:Examples:

>>> f.equals(f)
True
>>> g = f + 1
>>> f.equals(g)
False
>>> g -= 1
>>> f.equals(g)
True
>>> f.setprop('name', 'name0')
>>> g.setprop('name', 'name1')
>>> f.equals(g)
False
>>> f.equals(g, ignore=['name'])
True

'''
        # Check for object identity
        if self is other:
            return True

        # Check that each instance is of the same type
        if not ignore_type and not isinstance(other, self.__class__):
            if traceback:
                print("{0}: Incompatible types: {0}, {1}".format(
			self.__class__.__name__,
			other.__class__.__name__))
	    return False
        #--- End: if

        # ------------------------------------------------------------
        # Check the simple properties
        # ------------------------------------------------------------
        if ignore_fill_value:
            ignore += ('_FillValue', 'missing_value')

        self_properties  = set(self.properties()).difference(ignore)
        other_properties = set(other.properties()).difference(ignore)
        if self_properties != other_properties:
            if traceback:
                print("{0}: Different properties: {1}, {2}".format( 
                    self.__class__.__name__,
                    self_properties, other_properties))
            return False
        #--- End: if

        if rtol is None:
            rtol = RTOL()
        if atol is None:
            atol = ATOL()

        for prop in self_properties:
            x = self.getprop(prop)
            y = other.getprop(prop)

            if not cf_equals(x, y, rtol=rtol, atol=atol,
                             ignore_fill_value=ignore_fill_value,
                             traceback=traceback):
                if traceback:
                    print("{0}: Different {1}: {2!r}, {3!r}".format(
                        self.__class__.__name__, prop, x, y))
                return False
        #--- End: for

        # ------------------------------------------------------------
        # Check the special attributes
        # ------------------------------------------------------------
        self_special  = self._private['special_attributes']
        other_special = other._private['special_attributes']
        if set(self_special) != set(other_special):
            if traceback:
                print("{0}: Different attributes: {1}".format(
                    self.__class__.__name__,
                    set(self_special).symmetric_difference(other_special)))
            return False
        #--- End: if

        for attr, x in self_special.iteritems():
            y = other_special[attr]
            result = cf_equals(x, y, rtol=rtol, atol=atol,
                               ignore_data_type=ignore_data_type,
                               ignore_fill_value=ignore_fill_value,
                               traceback=traceback)
               
            if not result:
                if traceback:
                    print("{0}: Different {1}: {2!r}, {3!r}".format(
                          self.__class__.__name__, attr, x, y))
                return False
        #--- End: for

        # ------------------------------------------------------------
        # Check the data
        # ------------------------------------------------------------
        self_hasdata = self.hasdata
        if self_hasdata != other.hasdata:
            if traceback:
                print("{0}: Different data".format(self.__class__.__name__))
            return False

        if self_hasdata:
            if not self.data.equals(other.data, rtol=rtol, atol=atol,
                                    ignore_data_type=ignore_data_type,
                                    ignore_fill_value=ignore_fill_value,
                                    traceback=traceback):
                if traceback:
                    print("{0}: Different data".format(self.__class__.__name__))
                return False
        #--- End: if

        return True
    #--- End: def

    def expand_dims(self, position=0, copy=True):
        '''Insert a size 1 axis into the data array.

.. versionadded:: 1.6

.. seealso:: `squeeze`, `transpose`

:Examples 1:

>>> g = f.{+name}()

:Parameters:

    position: `int`, optional    
        Specify the position amongst the data array axes where the new
        axis is to be inserted. By default the new axis is inserted at
        position 0, the slowest varying position.

    {+copy}

:Returns:

    `None`

:Examples:

>>> v.{+name}(2)
>>> v.{+name}(-1)

        '''       
        if copy:
            v = self.copy()
        else:
            v = self

        if self.hasdata:
            v.data.expand_dims(position, copy=False)
        
        if v.hasbounds:
            position = self._parse_axes([position])[0]
            v.bounds.expand_dims(position, copy=False)

        return v
    #--- End: def
    
    def fill_value(self, default=None):
        '''Return the data array missing data value.

This is the value of the `missing_value` CF property, or if that is
not set, the value of the `_FillValue` CF property, else if that is
not set, ``None``. In the last case the default `numpy` missing data
value for the array's data type is assumed if a missing data value is
required.

.. versionadded:: 1.6

:Parameters:

    default: optional
        If the missing value is unset then return this value. By
        default, *default* is `None`. If *default* is the special
        value ``'netCDF'`` then return the netCDF default value
        appropriate to the data array's data type is used. These may
        be found as follows:

        >>> import netCDF4
        >>> print netCDF4.default_fillvals    

:Returns:

    out:
        The missing data value, or the value specified by *default* if
        one has not been set.

:Examples:

>>> f.{+name}()
None
>>> f._FillValue = -1e30
>>> f.{+name}()
-1e30
>>> f.missing_value = 1073741824
>>> f.{+name}()
1073741824
>>> del f.missing_value
>>> f.{+name}()
-1e30
>>> del f._FillValue
>>> f.{+name}()
None
>>> f,dtype
dtype('float64')
>>> f.{+name}(default='netCDF')
9.969209968386869e+36
>>> f._FillValue = -999
>>> f.{+name}(default='netCDF')
-999

        '''
        fillval = self._fill_value

        if fillval is None:
            if default == 'netCDF':
                dtype = self.data.dtype
                fillval = netCDF4.default_fillvals[d.kind + str(dtype.itemsize)]
            else:
                fillval = default 
        #--- End: if

        return fillval
    #--- End: def

    def setprop(self, prop, value):
        '''Set a CF or non-CF property.

.. versionadded:: 1.6

.. seealso:: `delprop`, `getprop`, `hasprop`

:Examples 1:

>>> f.setprop('standard_name', 'time')
>>> f.setprop('project', 'CMIP7')

:Parameters:

    prop: `str`
        The name of the property.

    value:
        The value for the property.

:Returns:

     `None`

        '''
#        # Still here? Then set a simple property
#        setattr(self._properties, 'prop', value)
#
#        self._property_names.add(prop)

        self._private['properties'][prop] = value
    #--- End: def

    def squeeze(self, axes=None, copy=True):
        '''Remove size 1 dimensions from the data array

.. versionadded:: 1.6

.. seealso:: `expand_dims`, `flip`, `transpose`

:Examples 1:

>>> f.{+name}()

:Parameters:

    axes: (sequence of) `int`, optional
        The size 1 axes to remove. By default, all size 1 axes are
        removed. Size 1 axes for removal are identified by their
        integer positions in the data array.
    
    {+copy}

:Returns:

    out: `{+Variable}`

:Examples:

>>> f.{+name}(1)
>>> f.{+name}([1, 2])

        '''
        if copy:
            v = self.copy()
        else:
            v = self

        if v.hasdata:
            v.data.squeeze(axes, copy=False)

#        if v.hasbounds:
#            axes = self._parse_axes(axes)
#            v.bounds.squeeze(axes, copy=False)

        return v
    #--- End: def

    def hasprop(self, prop):
        '''

Return True if a CF property exists, otherise False.

.. versionadded:: 1.6

.. seealso:: `delprop`, `getprop`, `setprop`

:Examples 1:

>>> if f.{+name}('standard_name'):
...     print 'Has standard name'

:Parameters:

    prop: `str`
        The name of the property.

:Returns:

     out: `bool`
         True if the CF property exists, otherwise False.

'''
        return prop in self._private['properties']
    #--- End: def

    @property
    def isscalar(self):
        '''True if the data array is scalar.

.. versionadded:: 1.6

.. seealso:: `hasdata`, `ndim`

:Examples:

>>> f.data.ndim
0
>>> f.isscalar
True

>>> f.data.ndim >= 1
True
>>> f.isscalar
False

>>> f.hasdata
False
>>> f.isscalar
False

        '''
        if not self.hasdata:
            return False

        return self.data.isscalar
    #--- End: def

    @property
    def isreftime(self):
        '''

.. versionadded:: 1.6

        '''
        units = self.getprop('units', None)
        if units is None:
            return bool(self.getprop('calendar', False))

        return 'since' in units
    #--- End: def

    @property
    def isvariable(self):
        '''True DCH

.. versionadded:: 1.6

:Examples:

>>> f.isvariable
True
        '''
        return True
    #--- End: def

    def identity(self, default=None, relaxed_identity=None):
        '''Return the identity of the {+variable}.

The identity is, by default, the first found of the following:

* The `standard_name` CF property.

* If the *relaxed_identity* parameter is True, the `long_name` CF property.

* The value of the *default* parameter.

This is altered if the *relaxed* parameter is True.

.. versionadded:: 1.6

.. seealso:: `name`

:Examples 1:

>>> i = f.{+name}()

:Parameters:

    default: optional
        The identity if one could not otherwise be found. By default,
        *default* is `None`.
        
:Returns:

    out:
        The identity.

:Examples 2:

>>> f.setprop('standard_name', 'Kelvin')
>>> f.id = 'foo'
>>> f.{+name}()
'Kelvin'
>>> f.delprop('standard_name')
>>> f.{+name}()
'foo'
>>> del f.id
>>> f.{+name}()
None
>>> f.{+name}('bar')
'bar'
>>> print f.{+name}()
None

        '''
        return self.name(default, identity=True, relaxed_identity=relaxed_identity)
    #--- End: def

    def insert_data(self, data, copy=True):
        '''Insert a new data array into the variable in place.

.. versionadded:: 1.6

:Parameters:

    data: `Data`

    copy: `bool`, optional

:Returns:

    `None`

        '''
        if not copy:
            self._Data = data
        else:
            self._Data = data.copy()
    #--- End: def

    def getprop(self, prop, *default):
        '''

Get a CF property.

When a default argument is given, it is returned when the attribute
doesn't exist; without it, an exception is raised in that case.

.. versionadded:: 1.6

.. seealso:: `delprop`, `hasprop`, `setprop`

:Examples 1:

>>> f.{+name}('standard_name')

:Parameters:

    prop: `str`
        The name of the CF property to be retrieved.

    default: optional
        Return *default* if and only if the variable does not have the
        named property.

:Returns:

    out:
        The value of the named property or the default value, if set.

:Examples 2:

>>> f.setprop('standard_name', 'air_temperature')
>>> f.{+name}('standard_name')
'air_temperature'
>>> f.delprop('standard_name')
>>> f.{+name}('standard_name')
AttributeError: Field doesn't have CF property 'standard_name'
>>> f.{+name}('standard_name', 'foo')
'foo'

'''        
        d = self._private['properties']

        if default:
            return d.get(prop, default[0])

        try:
            return d[prop]
        except KeyError:
            raise AttributeError("{} doesn't have CF property {}".format(
                self.__class__.__name__, prop))
    #--- End: def

    def delprop(self, prop):
        '''Delete a CF or non-CF property.

.. versionadded:: 1.6

.. seealso:: `getprop`, `hasprop`, `setprop`

:Examples 1:

>>> f.{+name}('standard_name')

:Parameters:

    prop: `str`
        The name of the property to be deleted.

:Returns:

     `None`

:Examples 2:

>>> f.setprop('project', 'CMIP7')
>>> f.{+name}('project')
>>> f.{+name}('project')
AttributeError: Can't delete non-existent property 'project'

        '''
        
        
#        # Delete a special attribute
#        if prop in self._special_properties:
#            delattr(self, prop)
#            return
#
#        # Still here? Then delete a simple attribute
#        try:
#            delattr(self.property, prop)
#        except AttributeError:
#            raise AttributeError("Can't delete non-existent property {!r}".format(prop))
#
#        self._property_names.discard(prop)
#        
        # Still here? Then delete a simple attribute
        try:
            del self._private['properties'][prop]
        except KeyError:
            raise AttributeError(
                "Can't delete non-existent CF property {!r}".format(prop))                    
    #--- End: def

    def name(self, default=None, identity=False, ncvar=True,
             relaxed_identity=None, id=True):
        '''Return a name for the {+variable}.

By default the name is the first found of the following:

  1. The `standard_name` CF property.
  
  2. The `long_name` CF property, preceeded by the string
     ``'long_name:'``.

  3. The `!id` attribute.

  4. The netCDF variable name as returned by the `ncvar` method.
  
  5. The value of the *default* parameter.

.. versionadded:: 1.6

.. seealso:: `identity`

:Examples 1:

>>> n = f.{+name}()
>>> n = f.{+name}(default='NO NAME')

:Parameters:

    default: optional
        If no name can be found then return the value of the *default*
        parameter. By default the default is `None`.

    identity: `bool`, optional
        If True then only 1., 3. and 5. are considered as possible
        names.
 
    ncvar: `bool`, optional
        If True then only 4. and 5. are considered as possible names.

:Returns:

    out:
        The name.

:Examples 2:

>>> f.setprop('standard_name', 'air_temperature')
>>> f.setprop('long_name', 'temperature of the air')
>>> f.ncvar('tas')
>>> f.{+name}()
'air_temperature'
>>> f.delprop('standard_name')
>>> f.{+name}()
'long_name:temperature of the air'
>>> f.delprop('long_name')
>>> f.{+name}()
'ncvar%tas'
>>> f.ncvar(None)
>>> f.{+name}()
None
>>> f.{+name}('no_name')
'no_name'
>>> f.setprop('standard_name', 'air_temperature')
>>> f.{+name}('no_name')
'air_temperature'

        '''
        if relaxed_identity is None:
            relaxed_identity = RELAXED_IDENTITIES()

#        if ncvar:
#            if identity:
#                raise ValueError(
#"Can't find identity/ncvar: ncvar and identity parameters can't both be True")
#
#            if relaxed_identity:
#                raise ValueError(
#"Can't find identity/ncvar: ncvar and relaxed_identity parameters can't both be True")
#
#            n = getattr(self, 'ncvar', None)
#            if n is not None:
#                return 'ncvar%{0}'.format(n)
#            
#            return default
#        #--- End: if

        n = self.getprop('standard_name', None)
        if n is not None:
            return n

        if identity or relaxed_identity:
            n = getattr(self, 'id', None)
            if n is not None:
#                return 'id%{0}'.format(n) #n
                return n
            if not relaxed_identity:
                return default


        n = self.getprop('long_name', None)
        if n is not None:
            return 'long_name:{0}'.format(n)

        if not relaxed_identity:
            n = getattr(self, 'id', None)
            if n is not None:
                return 'id%{0}'.format(n) #n

        if ncvar:
            n = self.ncvar()
            if n is not None:
                return 'ncvar%{0}'.format(n)
            
        return default
    #--- End: def

    def ncvar(self, *name):
        '''
        '''
        if not name:
            return self._ncvar


        name = name[0]
        self._ncvar = name

        return name
    #--- End: def
    
    def open(self):
        '''
'''
        if self.hasdata:
            self.data.open()
    #--- End: def

    def HDF_chunks(self, *chunksizes):
        '''{+HDF_chunks}
        
.. versionadded:: 1.6

:Examples 1:
        
To define chunks which are the full size for each axis except for the
first axis which is to have a chunk size of 12:

>>> old_chunks = f.{+name}({0: 12})

:Parameters:

    {+chunksizes}

:Returns:

    out: `dict`
        The chunk sizes prior to the new setting, or the current
        current sizes if no new values are specified.

        '''
        if self.hasdata:
            old_chunks = self.data.HDF_chunks(*chunksizes)
        else:
            old_chunks = None

        if self.hasbounds:
            self.bounds.HDF_chunks(*chunksizes)

        return old_chunks
    #--- End: def

    def properties(self, props=None, clear=False, copy=True):
        '''Inspect or change the CF properties.

.. versionadded:: 1.6

:Examples 1:

>>> f.{+name}()

:Parameters:

    props: `dict`, optional   
        Set {+variable} attributes from the dictionary of values. If
        the *copy* parameter is True then the values in the *attrs*
        dictionary are deep copied

    clear: `bool`, optional
        If True then delete all CF properties.

    copy: `bool`, optional
        If False then any property values provided bythe *props*
        parameter are not copied before insertion into the
        {+variable}. By default they are deep copied.

:Returns:

    out: `dict`
        The CF properties prior to being changed, or the current CF
        properties if no changes were specified.

:Examples 2:

        '''
#        if copy:            
        out = deepcopy(self._private['properties'])
#        else:
#            out = self._simple_properties().copy()
            
#        # Include properties that are not listed in the simple
#        # properties dictionary
#        for prop in ('units', 'calendar'):
#            _ = getattr(self, prop, None)
#            if _ is not None:
#                out[prop] = _
#        #--- End: for

        if clear:
            self._private['properties'].clear()
            return out

        if not props:
            return out

        setprop = self.setprop
        delprop = self.delprop
        if copy:
            for prop, value in props.iteritems():
                if value is None:
                    # Delete this property
                    delprop(prop)
                else:
                    setprop(prop, deepcopy(value))
        else:
            for prop, value in props.iteritems():
                if value is None:
                    # Delete this property
                    delprop(prop)
                else:
                    setprop(prop, value)

        return out
    #--- End: def

#    def attributes(self, attrs=None, copy=True):
#        '''Inspect or change attributes which are not CF properties.
#
#.. versionadded:: 1.6
#
#:Examples 1:
#
#>>> f.{+name}()
#
#:Parameters:
#
#    attrs: `dict`, optional
#        Set {+variable} attributes from the dictionary of values. If
#        the *copy* parameter is True then the values in the *attrs*
#        dictionary are deep copied
#
#    copy: `bool`, optional
#        If True then the values in the returned dictionary are deep
#        copies of the {+variable}'s attribute values. By default they
#        are not copied.
#
#:Returns:
#
#    out: `dict`
#
#:Examples:
#
#>>> f.{+name}()
#{}
#>>> f.foo = 'bar'
#>>> f.{+name}()
#{'foo': 'bar'}
#>>> f.{+name}().pop('foo')
#'bar'
#>>> f.{+name}()
#{'foo': 'bar'}
#
#>>> f.{+name}({'name': 'value'})
#{'foo': 'bar', 'name': 'value'}
#
#        ''' 
# 
#        out = deepcopy(self.__dict__)
#
#        del out['_hasbounds']
#        del out['_hasdata']
#        del out['_private']
#        
#        if not attrs:
#            return out
#
#        if copy:
#            for attr, value in attrs.iteritems():
#                setattr(self, attr, deepcopy(value))
#        else:
#            for attr, value in attrs.iteritems():
#                setattr(self, attr, value)
#
#        return out
#    #--- End: def

#--- End: class