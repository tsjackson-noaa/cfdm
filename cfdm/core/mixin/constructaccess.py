from builtins import object
from future.utils import with_metaclass

import abc


class ConstructAccess(with_metaclass(abc.ABCMeta, object)):
    '''Mixin class for manipulating a `Constructs` object.

    '''   
    @abc.abstractmethod
    def _get_constructs(self, *default):
        '''Return the `Constructs` object

:Parameters:

    default: optional
        If set then return *default* if there is no `Constructs` object.
:Returns:

    out:
        The `Constructs` object. If unset then return *default* if provided.

**Examples**

>>> c = f._get_constructs()
>>> c = f._get_constructs(None)

        '''
        raise NotImplementedError()
    #--- End: def
    
    def array_constructs(self, copy=False):
        return self._get_constructs().array_constructs(copy=copy)
    
    def auxiliary_coordinates(self, copy=False):
        '''Return the auxiliary coordinate constructs.

.. versionadded:: 1.7

.. seealso:: `constructs`

:Parameters:

    copy: `bool`, optional

:Returns:

    out: `dict`

**Examples**

>>> f.auxiliary_constructs()
{}
        '''
        return self._get_constructs().constructs(construct_type='auxiliary_coordinate', copy=copy)
    
    def cell_measures(self, copy=False):
        '''Return the cell measure constructs.

.. versionadded:: 1.7

.. seealso:: `constructs`

:Parameters:

    copy: `bool`, optional

:Returns:

    out: `dict`

**Examples**

>>> f.cell_measure()
{}
        '''
        return self._get_constructs().constructs(construct_type='cell_measure', copy=copy)
    
    def construct_axes(self, id=None):
        '''Return the identifiers of the domain axes spanned by the construct
data array.

.. versionadded:: 1.7

.. seealso:: `constructs`, `get_construct`

:Parameters:

    id: `str`
        The identifier of the construct.

:Returns:

    out: `tuple` or `None`
        The identifiers of the domain axes spanned by the construct's
        data array. If the construct does not have a data array then
        `None` is returned.

**Examples**

>>> f.construct_axes('auxiliarycoordinate0')
('domainaxis1', 'domainaxis0')
>>> print(f.construct_axes('auxiliarycoordinate99'))
None

        '''
        return self._get_constructs().construct_axes(id=id)
    #--- End: def
    
    def construct_type(self, id):
        '''TODO
        '''                
        return self._get_constructs().construct_type(id)
    #--- End: def
    
    def constructs(self, copy=False):
        '''Return the metadata constructs.

.. versionadded:: 1.7

.. seealso:: `construct_axes`

:Parameters:

    copy: `bool`, optional

:Returns:

    out: `dict`

**Examples**

>>> f.constructs()
{}

        '''
        return self._get_constructs().constructs(copy=copy)
    #--- End: def
    
    def coordinate_references(self, copy=False):
        '''Return the coordinate reference constructs.

.. versionadded:: 1.7

.. seealso:: `constructs`

:Parameters:

    copy: `bool`, optional

:Returns:

    out: `dict`

**Examples**

>>> f.coordinate_references()
{}
        '''
        return self._get_constructs().constructs(construct_type='coordinate_reference', copy=copy)
    
    def coordinates(self, copy=False):
        '''Return the dimension and auxiliar coordinate constructs.

.. versionadded:: 1.7

.. seealso:: `constructs`

:Parameters:

    copy: `bool`, optional

:Returns:

    out: `dict`

**Examples**

>>> f.coordinates()
{}
        '''
        out = self.dimension_coordinates(copy=copy)
        out.update(self.auxiliary_coordinates(copy=copy))
        return out
    #--- End: def

    @abc.abstractmethod
    def del_construct(self, id):
        '''REQUIRES DOCUMENTATION
        '''
        raise NotImplementedError()
    #--- End: def

    def get_construct(self, id):
        '''Return a metadata construct.

:Parameters:

    id: `str`

:Returns:

    out:

**Examples**

>>> f.constructs()
>>> f.get_construct('dimensioncoordinate1')
<>
>>> f.get_construct('dimensioncoordinate99', 'Not set')
'Not set'
        '''
        return self._get_constructs().get_construct(id)
    #--- End: def

    def dimension_coordinates(self, copy=False):
        '''Return the dimension coordinate constructs.

.. versionadded:: 1.7

.. seealso:: `constructs`

:Parameters:

    copy: `bool`, optional

:Returns:

    out: `dict`

**Examples**

>>> f.dimension_coordinates()
{}
        '''
        return self._get_constructs().constructs(construct_type='dimension_coordinate', copy=copy)
    #--- End: def
    
    def domain_ancillaries(self, copy=False):
        '''Return the domain ancillary constructs.

.. versionadded:: 1.7

.. seealso:: `constructs`

:Parameters:

    copy: `bool`, optional

:Returns:

    out: `dict`

**Examples**

>>> f.domain_ancillaries()
{}
        '''
        return self._get_constructs().constructs(construct_type='domain_ancillary', copy=copy)
    #--- End: def
    
    def domain_axes(self, copy=False):
        '''Return the domain axis constructs.

.. versionadded:: 1.7

.. seealso:: `constructs`

:Parameters:

    copy: `bool`, optional

:Returns:

    out: `dict`

**Examples**

>>> f.domain_axes()
{}
        '''
        return self._get_constructs().constructs(construct_type='domain_axis', copy=copy)
    #--- End: def
        
    def domain_axis_name(self, axis):
        '''
        '''
        return self._get_constructs().domain_axis_name(axis)
    #--- End: def
    
    def set_auxiliary_coordinate(self, item, id=None, axes=None,
                                 copy=True, replace=True):
        '''Insert an auxiliary coordinate construct.
        '''
        if not replace and id in self.auxiliary_coordinates():
            raise ValueError(
"Can't insert auxiliary coordinate construct: Identifier {!r} already exists".format(id))

        return self.set_construct('auxiliary_coordinate', item,
                                  key=id, axes=axes, copy=copy)
    #--- End: def

    def set_domain_axis(self, domain_axis, key=None, replace=True, copy=True):
        '''Insert a domain axis construct.
        '''
        axes = self.domain_axes()
        if (not replace and
            key in axes and
            axes[key].get_size() != domain_axis.get_size()):
            raise ValueError(
"Can't insert domain axis: Existing domain axis {!r} has different size (got {}, expected {})".format(
    key, domain_axis.get_size(), axes[key].get_size()))

        return self.set_construct('domain_axis',
                                  domain_axis, key=key, copy=copy)
    #--- End: def

    def set_domain_ancillary(self, item, key=None, axes=None,
                             extra_axes=0, copy=True, replace=True):
        '''Insert a domain ancillary construct.
        '''       
        if not replace and key in self.domain_ancillaries():
            raise ValueError(
"Can't insert domain ancillary construct: Identifier {0!r} already exists".format(key))

        return self.set_construct('domain_ancillary', item, key=key,
                                  axes=axes, extra_axes=extra_axes,
                                  copy=copy)
    #--- End: def

    def set_construct(self, construct_type, construct, key=None,
                      axes=None, extra_axes=0, replace=True,
                      copy=True):
        '''Insert a construct.
        '''
        return self._get_constructs().set_construct(construct_type,
                                                    construct,
                                                    key=key,
                                                    axes=axes,
                                                    extra_axes=extra_axes,
                                                    replace=replace,
                                                    copy=copy)
    #--- End: def

    def set_construct_axes(self, key, axes):
        '''
        '''
        return self._get_constructs().set_construct_axes(key, axes)
    #--- End: def

    def set_cell_measure(self, item, key=None, axes=None, copy=True, replace=True):
        '''
        '''
        if not replace and key in self.cell_measures():
            raise ValueError(
"Can't insert cell measure construct: Identifier {0!r} already exists".format(key))

        return self.set_construct('cell_measure', item, key=key,
                                  axes=axes, copy=copy)
    #--- End: def

    def set_coordinate_reference(self, item, key=None, axes=None,
                                    copy=True, replace=True):
        '''
        '''
        return self.set_construct('coordinate_reference',
                                  item, key=key, copy=copy)
    #--- End: def

    def set_dimension_coordinate(self, item, key=None, axes=None, copy=True, replace=True):
        '''
        '''
        if not replace and key in self.dimension_coordinates():
            raise ValueError(
"Can't insert dimension coordinate construct: Identifier {!r} already exists".format(key))

        return self.set_construct('dimension_coordinate',
                                  item, key=key, axes=axes, copy=copy)
    #--- End: def

#--- End: class
