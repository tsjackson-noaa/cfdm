import abc

from .properties import Properties


# ====================================================================
#
# ArrayConstruct object
#
# ====================================================================

class PropertiesData(Properties):
    '''Base class for storing a data array with metadata.

A variable contains a data array and metadata comprising properties to
describe the physical nature of the data.

All components of a variable are optional.

    '''
    __metaclass__ = abc.ABCMeta

    def __init__(self, properties={}, data=None, source=None,
                 copy=True, _use_data=True):
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
        super(PropertiesData, self).__init__(properties=properties,
                                             source=source, copy=copy)
        
        if source is not None:
            if _use_data and data is None:
                data = source.get_data(None)
        #--- End: if

        if _use_data and data is not None:
            self.set_data(data, copy=copy)
    #--- End: def

    def __data__(self):
        '''
        '''
        data = self.get_data(None)
        if data is None:
            raise ValueError("sdif n;u3jnr42[ 4890yh 8u;jkb")

        return data
    #--- End: def
    
    # ----------------------------------------------------------------
    # Attribute (read only)
    # ----------------------------------------------------------------
    @property
    def dtype(self):
        '''asdasds

:Examples:


        '''
        return self.get_data().dtype
    #--- End: def

    # ----------------------------------------------------------------
    # Attribute (read only)
    # ----------------------------------------------------------------
    @property
    def ndim(self):
        '''Tasasds

:Examples:

        '''
        return self.get_data().ndim
    #--- End: def

    # ----------------------------------------------------------------
    # Attribute (read only)
    # ----------------------------------------------------------------
    @property
    def size(self):
        '''Number of elements in the data array.

:Examples:


        '''
        return self.get_data().size
    #--- End: def

    # ----------------------------------------------------------------
    # Attribute (read only)
    # ----------------------------------------------------------------
    @property
    def shape(self):
        '''asdasds

:Examples:

>>> d.shape
(73, 96)
>>> d.size
7008

>>> d.shape
(1, 1, 1)
>>> d.size
1

>>> d.ndim
0
>>> d.shape
()
>>> d.size
1

        '''
        return self.get_data().shape
    #--- End: def

    def copy(self, data=True):
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
        return type(self)(source=self, copy=True, _use_data=data)
    #--- End: def

    def del_data(self):
        '''Remove and return the data array.

.. versionadded:: 1.6

.. seealso:: `get_data`, `set_data`

:Returns: 

    out: `Data` or `None`
        The removed data array, or `None` if there isn't one.

:Examples:

>>> f.hasdata
True
>>> print f.data
[0, ..., 9] m
>>> d = f.del_data()
>>> print d
[0, ..., 9] m
>>> f.hasdata
False
>>> print f.del_data()
None

        '''
        return self._del_component(3, 'data')
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
        fillval = self.get_property('_FillValue', None)

        if fillval is None:
            if default == 'netCDF':
                d = self.get_data().dtype
                fillval = netCDF4.default_fillvals[d.kind + str(d.itemsize)]
            else:
                fillval = default 
        #--- End: if

        return fillval
    #--- End: def

    def get_array(self):
        '''A numpy array copy the data.

:Examples:

>>> d = Data([1, 2, 3.0], 'km')
>>> a = d.array
>>> isinstance(a, numpy.ndarray)
True
>>> print a
[ 1.  2.  3.]
>>> d[0] = -99 
>>> print a[0] 
1.0
>>> a[0] = 88
>>> print d[0]
-99.0 km

        '''
        data = self.get_data(None)
        if data is None:
            raise ValueError("No array to get")
        
        return data.get_array()
    #--- End: def

    def get_data(self, *default):
        '''
:Parameters:

    default: optional

        '''
        try:
            data = self._get_component(3, 'data', None, None)
        except AttributeError:
            raise AttributeError("There is no data")

        if data is None and default:
            return default[0]
        
        units = self.get_property('units', None)
        if units is not None:
            data.set_units(units)

        calendar = self.get_property('calendar', None)
        if calendar is not None:
            data.set_calendar(calendar)

        return data        
    #--- End: def

    def has_data(self):
        '''True if there is a data array.
        
If present, the data array is stored in the `data` attribute.

.. versionadded:: 1.6

.. seealso:: `data`

:Examples:

>>> if f.has_data():
...     print f.data

        '''     
        return self._has_component(3, 'data')
    #--- End: def

    def set_data(self, data, copy=True):
        '''Insert a new data array into the variable in place.

.. versionadded:: 1.6

:Parameters:

    data: `Data`

    copy: `bool`, optional

:Returns:

    `None`

        '''
        if copy:
            data = data.copy()

        data.set_units(None)
        data.set_calendar(None)
        
        self._set_component(3, 'data', None, data)
    #--- End: def

#--- End: class
