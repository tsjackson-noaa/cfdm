import abc

from .coordinate import Coordinate

# ====================================================================
#
# AuxiliaryCoordinate object
#
# ====================================================================

class AuxiliaryCoordinate(Coordinate):
    '''A CF auxiliary coordinate construct.

    '''
    __metaclass__ = abc.ABCMeta
      
    def dump(self, display=True, _omit_properties=None, field=None,
             key=None, _level=0, _title=None):
        '''Return a string containing a full description of the auxiliary
coordinate object.

:Parameters:

    display: `bool`, optional
        If False then return the description as a string. By default
        the description is printed, i.e. ``f.dump()`` is equivalent to
        ``print f.dump(display=False)``.

:Returns:

    out: `None` or `str`
        A string containing the description.

:Examples:

        '''
        if _title is None:
            _title = 'Auxiliary coordinate: ' + self.name(default='')

        return super(AuxiliaryCoordinate, self).dump(
            display=display,
            field=field, key=key,
             _level=_level, _title=_title,
            _omit_properties=_omit_properties)
    #--- End: def

    
#--- End: class
