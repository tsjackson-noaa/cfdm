from builtins import super

from . import mixin
from . import core


class FieldAncillary(mixin.NetCDFVariable,
                     mixin.PropertiesData,
                     core.FieldAncillary):
    '''A field ancillary construct of the CF data model.

The field ancillary construct provides metadata which are distributed
over the same sampling domain as the field itself. For example, if a
data variable holds a variable retrieved from a satellite instrument,
a related ancillary data variable might provide the uncertainty
estimates for those retrievals (varying over the same spatiotemporal
domain).

The field ancillary construct consists of an array of the ancillary
data, which is zero-dimensional or which depends on one or more of the
domain axes, and properties to describe the data. It is assumed that
the data do not depend on axes of the domain which are not spanned by
the array, along which the values are implicitly propagated. CF-netCDF
ancillary data variables correspond to field ancillary
constructs. Note that a field ancillary construct is constrained by
the domain definition of the parent field construct but does not
contribute to the domain's definition, unlike, for instance, an
auxiliary coordinate construct or domain ancillary construct.

.. versionadded:: 1.7

    '''
    def __init__(self, properties=None, data=None, source=None,
                 copy=True, _use_data=True):

        '''**Initialization**

:Parameters:

    properties: `dict`, optional
       Set descriptive properties. The dictionary keys are property
       names, with corresponding values. Ignored if the *source*
       parameter is set.

       *Example:*
          ``properties={'standard_name': 'altitude'}``

       Properties may also be set after initialisation with the
       `properties` and `set_property` methods.

    data: `Data`, optional
        Set the data array. Ignored if the *source* parameter is set.

        The data array may also be set after initialisation with the
        `set_data` method.

    source: optional
        Initialize the properties and data from those of *source*.

    copy: `bool`, optional
        If False then do not deep copy input parameters prior to
        initialization. By default arguments are deep copied.

        '''
        super().__init__(properties=properties, data=data,
                         source=source, copy=copy,
                         _use_data=_use_data)
        
        self._initialise_netcdf(source)
    #--- End: def
    
    def dump(self, display=True, _omit_properties=None, field=None,
             key=None, _level=0, _title=None, _axes=None,
             _axis_names=None):
        '''A full description of the field ancillary construct.

Returns a description of all properties, including those of
components, and provides selected values of all data arrays.

.. versionadded:: 1.7

:Parameters:

    display: `bool`, optional
        If False then return the description as a string. By default
        the description is printed.

:Returns:

    out: `None` or `str`
        The description. If *display* is True then the description is
        printed and `None` is returned. Otherwise the description is
        returned as a string.

        '''
        if _title is None:
            _title = 'Field Ancillary: ' + self.name(default='')

        return super().dump(display=display, field=field, key=key,
                            _omit_properties=_omit_properties,
                            _level=_level, _title=_title, _axes=_axes,
                            _axis_names=_axis_names)
    #--- End: def
    
    def equals(self, other, rtol=None, atol=None, traceback=False,
               ignore_data_type=False, ignore_fill_value=False,
               ignore_properties=(), ignore_construct_type=False):
        '''Whether two field ancillary constructs are the same.

Equality is strict by default. This means that:

* the descriptive properties must be the same,

..

* vector-valued properties must have same size and be element-wise
  equal,

..

* if there are data arrays then they must have same shape, data type
  and be element-wise equal.

Two numerical elements ``a`` and ``b`` are considered equal if
``|a-b|<=atol+rtol|b|``, where ``atol`` (the tolerance on absolute
differences) and ``rtol`` (the tolerance on relative differences) are
positive, typically very small numbers.

.. versionadded:: 1.7

:Parameters:

    other: 
        The object to compare for equality.

    atol: float, optional
        The tolerance on absolute differences between real
        numbers. The default value is set by the `cfdm.ATOL` function.
        
    rtol: float, optional
        The tolerance on relative differences between real
        numbers. The default value is set by the `cfdm.RTOL` function.

    ignore_fill_value: `bool`, optional
        If True then the "_FillValue" and "missing_value" properties
        are omitted from the comparison.

    traceback: `bool`, optional
        If True and the collections of properties are different then
        print a traceback stating how they are different.

    ignore_properties: sequence of `str`, optional
        The names of properties to omit from the comparison.

    ignore_data_type: `bool`, optional
        TODO

    ignore_construct_type: `bool`, optional
        If True then *other* can be equal if it is not a field
        ancillary construct (nor a subclass of one), but is an object
        with the same API. By default, *other* can only be equal if it
        is a field ancillary construct (or a subclass of one).

:Returns: 
  
    out: `bool`
        Whether the two field ancillary constructs are equal.

**Examples:**

>>> f.equals(p)
True
>>> f.equals(d.copy())
True
>>> f.equals('not a field ancillary')
False

>>> g = f.copy()
>>> g.set_property('foo', 'bar')
>>> f.equals(g)
False
>>> f.equals(g, traceback=True)
FieldAncillary: Non-common property name: foo
FieldAncillary: Different properties
False

        '''
        return super().equals(other, rtol=rtol, atol=atol,
                              traceback=traceback,
                              ignore_data_type=ignore_data_type,
                              ignore_fill_value=ignore_fill_value,
                              ignore_properties=ignore_properties,
                              ignore_construct_type=ignore_construct_type)
    #--- End: def
    
#--- End: class
