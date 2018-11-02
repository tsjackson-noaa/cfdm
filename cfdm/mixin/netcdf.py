from builtins import object


class NetCDF(object):
    '''Mixin

    '''

    def _initialise_netcdf(self, source=None):
        '''TODO 
        '''
        if source is None:
             netcdf = {}
        else:        
            try:
                netcdf = source._get_component('netcdf', None).copy()
            except AttributeError:
                netcdf = {}
        #--- End: if
        
        self._set_component('netcdf', netcdf, copy=False)
    #--- End: def

#--- End: class


class NetCDFDimension(NetCDF):
    '''Mixin TODO 

    '''

#    def _initialise_ncdim_from(self, source):
#        '''
#        '''
#        try:
#            ncdim = source.nc_get_dimension(None)
#        except AttributeError:
#            ncdim = None##
#
#        if ncdim is not None:
#            self.nc_set_dimension(ncdim)
#    #--- End: def

    def nc_del_dimension(self, *default):
        '''TODO 
        '''
        try:
            return self._get_component('netcdf').pop('dimension', *default)
        except KeyError:
            raise AttributeError("{!r} object has no netCDF dimension name".format(self.__class__.__name__))
    #--- End: def

    def nc_get_dimension(self, *default):
        '''ttttttttt TODO 
        '''
        try:
            return self._get_component('netcdf')['dimension']
        except KeyError:
            if default:
                return default[0]

            raise AttributeError("{!r} has no netCDF dimension name".format(
                self.__class__.__name__))
    #--- End: def

    def nc_has_dimension(self):
        '''TODO 
        '''
        return 'dimension' in self._get_component('netcdf')
    #--- End: def

    def nc_set_dimension(self, value):
        '''TODO 
        '''
        self._get_component('netcdf')['dimension'] = value
    #--- End: def

#--- End: class


class NetCDFVariable(NetCDF):
    '''Mixin TODO 

    '''

#    def _initialise_ncvar_from(self, source):
#        '''
#        '''
#        try:
#            ncvar = source.nc_get_variable(None)
#        except AttributeError:
#            ncvar = None
#
#        if ncvar is not None:
#            self.nc_set_variable(ncvar)
#    #--- End: def

    def nc_del_variable(self, *default):
        '''TODO 
        '''        
        try:
            return self._get_component('netcdf').pop('variable', *default)
        except KeyError:
            raise AttributeError("{!r} object has no netCDF variable name".format(self.__class__.__name__))
    #--- End: def
        
    def nc_get_variable(self, *default):
        '''ttttttttt TODO 
        '''
        try:
            return self._get_component('netcdf')['variable']
        except KeyError:
            if default:
                return default[0]

            raise AttributeError("{!r} has no netCDF variable name".format(
                self.__class__.__name__))
    #--- End: def

    def nc_has_variable(self):
        '''TODO 
        '''
        return 'variable' in self._get_component('netcdf')
    #--- End: def

    def nc_set_variable(self, value):
        '''TODO 
        '''
        self._get_component('netcdf')['variable'] = value
    #--- End: def

#--- End: class


class NetCDFSampleDimension(NetCDF):
    '''Mixin TODO 

    '''
    def nc_del_sample_dimension(self, *default):
        '''TODO 
        '''        
        try:
            return self._get_component('netcdf').pop('sample_dimension', *default)
        except KeyError:
            raise AttributeError("{!r} object has no netCDF sample dimension name".format(self.__class__.__name__))
    #--- End: def

    def nc_get_sample_dimension(self, *default):
        '''ttttttttt TODO 
        '''
        try:
            return self._get_component('netcdf')['sample_dimension']
        except KeyError:
            if default:
                return default[0]

            raise AttributeError("{!r} has no netCDF sample dimension name".format(
                self.__class__.__name__))
    #--- End: def

    def nc_has_sample_dimension(self):
        '''TODO 
        '''
        return 'sample_dimension' in self._get_component('netcdf')
    #--- End: def

    def nc_set_sample_dimension(self, value):
        '''TODO 
        '''
        self._get_component('netcdf')['sample_dimension'] = value
    #--- End: def

#--- End: class

class NetCDFInstanceDimension(NetCDF):
    '''Mixin TODO 

    '''
    def nc_del_instance_dimension(self,*default):
        '''TODO 
        '''        
        try:
            return self._get_component('netcdf').pop('instance_dimension', *default)
        except KeyError:
            raise AttributeError("{!r} object has no netCDF instance dimension name".format(self.__class__.__name__))
    #--- End: def

    def nc_get_instance_dimension(self, *default):
        '''ttttttttt TODO 
        '''
        try:
            return self._get_component('netcdf')['instance_dimension']
        except KeyError:
            if default:
                return default[0]

            raise AttributeError("{!r} has no netCDF instance dimension name".format(
                self.__class__.__name__))
    #--- End: def

    def nc_has_instance_dimension(self):
        '''TODO 
        '''
        return 'instance_dimension' in self._get_component('netcdf')
    #--- End: def

    def nc_set_instance_dimension(self, value):
        '''TODO 
        '''
        self._get_component('netcdf')['instance_dimension'] = value
    #--- End: def

#--- End: class


class NetCDFDataVariable(NetCDF):
    '''Mixin TODO 

    '''
    def nc_global_attributes(self, attributes=None):
        '''TODO
        '''
        out = self._get_component('netcdf').get('global_attributes')
        
        if out is None:
            out = ()

        if attributes:
            self._get_component('netcdf')['global_attributes'] = tuple(attributes)

        return list(out)
    #--- End: def
    
    def nc_unlimited_axes(self, axes=None):
        '''TODO 
        '''
        out = self._get_component('netcdf').get('unlimited_axes')

        if out is None:
            out = ()

        if axes:
            self._get_component('netcdf')['unlimited_axes'] = tuple(axes)

        return list(out)
    #--- End: def

#--- End: class

