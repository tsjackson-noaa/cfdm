from collections import abc
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

class AbstractArrayConstructCore(object):
    '''

Base class for storing a data array with metadata.

A variable contains a data array and metadata comprising properties to
describe the physical nature of the data.

All components of a variable are optional.

'''
    __metaclass__ = abc.ABCMeta

    _special_properties = set(('_FillValue',
                               'missing_value'))

    def __init__(self, properties={}, data=None, source=None,
                 copy=True):
        '''**Initialization**

:Parameters:

    properties: `dict`, optional
        Initialize properties from the dictionary's key/value pairs.

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
        #--- End: if

        if properties:
            self.properties(properties, copy=copy)

        if data is not None:
            self.insert_data(data, copy=copy)
    #--- End: def

    def __deepcopy__(self, memo):
        '''

Called by the :py:obj:`copy.deepcopy` standard library function.

.. versionadded:: 1.6

'''
        return self.copy()
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

    def name(self, default=None, ncvar=True):
        '''Return a name for the {+variable}.

By default the name is the first found of the following:

  1. The `standard_name` CF property.
  
  2. The `long_name` CF property, preceeded by the string
     ``'long_name:'``.

  3. If the *ncvar* parameter is True, the netCDF variable name as
     returned by the `ncvar` method, preceeded by the string
     ``'ncvar%'``.
  
  4. The value of the *default* parameter.

.. versionadded:: 1.6

:Examples 1:

>>> n = f.{+name}()
>>> n = f.{+name}(default='NO NAME')

:Parameters:

    default: optional
        If no name can be found then return the value of the *default*
        parameter. By default the default is `None`.

    ncvar: `bool`, optional

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
        n = self.getprop('standard_name', None)
        if n is not None:
            return n

        n = self.getprop('long_name', None)
        if n is not None:
            return 'long_name:{0}'.format(n)

        if ncvar:
            n = self.ncvar()
            if n is not None:
                return 'ncvar%{0}'.format(n)
            
        return default
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
                d = self.data.dtype
                fillval = netCDF4.default_fillvals[d.kind + str(d.itemsize)]
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
    def isvariable(self):
        '''True DCH

.. versionadded:: 1.6

:Examples:

>>> f.isvariable
True
        '''
        return True
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

#        if self.hasbounds:
#            self.bounds.HDF_chunks(*chunksizes)

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

#--- End: class
