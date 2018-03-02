import sys

import numpy

from .array import Array

class GatheredArray(Array):
    '''A numpy  array.

    '''
    def __init__(self, array=None, shape=None, size=None, ndim=None,
                 compression=None):
        '''
        
**Initialization**

:Parameters:

    array: `numpy.ndarray`

        '''
        self.array  = array

        self._shape = shape
        self._size  = size
        self._ndim  = ndim

        self._compression = compression
    #--- End: def

    def __getitem__(self, indices):
        '''x.__getitem__(indices) <==> x[indices]

Returns an independent numpy array.

        '''
        (compression_type, uncompression) = self._compression.items()[0]
        
        if compression_type == 'gathered':
            uarray = numpy.ma.masked_all(self.shape, dtype=self.dtype)
            
            sample_axis           = uncompression['axis']
            uncompression_indices = uncompression['indices']
            
            compressed_axes = range(sample_axis, self.ndim - (array.ndim - sample_axis - 1))
            n_compressed_axes = len(compressed_axes)
            
            zzz = [reduce(mul, [shape[i] for i in compressed_axes[i:]], 1)
                   for i in range(1, n_compressed_axes)]

            sample_indices = [slice(None)] * self.array.ndim
            u_indices      = [slice(None)] * self.ndim        
        

            zeros = [0] * n_compressed_axes
            for ii, b in enumerate(uncompression_indices):
                sample_indices[sample_axis] = ii
                
                xxx = zeros[:]
                for i, z in enumerate(zzz):                
                    if b >= z:
                        (a, b) = divmod(b, z)
                        xxx[i] = a
                    xxx[-1] = b
                #--- End: for
                        
                for j, x in izip(compressed_axes, xxx):
                    u_indices[j] = x
                    
                uarray[u_indices] = array[sample_indices]
            #--- End: for

        elif compression_type == 'DSG_contiguous':
            # Create an empty Data array which has dimensions (instance
            # dimension, element dimension).
            uarray = numpy.ma.masked_all(self.shape, dtype=self.dtype)

            elements_per_instance = uncompression['elements_per_instance']
            
            start = 0 
            for i, n in enumerate(elements_per_instance):
                n = int(n)
                sample_indices = slice(start, start + n)
                
                u_indices = (slice(i, i+1),
                             slice(0, sample_indices.stop - sample_indices.start))
                
                uarray[u_indices] = array[sample_indices]
                
                start += n
            #--- End: for

        elif compression_type == 'DSG_indexed':
            # Create an empty Data array which has dimensions (instance
            # dimension, element dimension).
            array = self.array
            
            uarray = numpy.ma.masked_all(self.shape, dtype=self.dtype)

            for i in range(uarray.shape[0]):
                sample_dimension_indices = numpy.where(index == i)[0]
                
                u_indices = (slice(i, i+1),
                           slice(0, len(sample_dimension_indices)))
                
                uarray[u_indices] = array[sample_dimension_indices]
            #--- End: for

        elif compression_type == 'DSG_indexed_contiguous':
            array = self.array

            uarray = numpy.ma.masked_all(self.shape, dtype=self.dtype)

            elements_per_profile = uncompression['elements_per_profile']
            
            # Loop over instances
            for i in range(uarray.shape[0]):

                # For all of the profiles in ths instance, find the
                # locations in the elements_per_profile array of the
                # number of elements in the profile
                xprofile_indices = numpy.where(profile_indices == i)[0]
                
                # Find the number of profiles in this instance
                n_profiles = xprofile_indices.size
                
                # Loop over profiles in this instance
                for j in range(uarray.shape[1]):
                    if j >= n_profiles:
                        continue
                
                    # Find the location in the elements_per_profile array
                    # of the number of elements in this profile
                    profile_index = xprofile_indices[j]
                    
                    if profile_index == 0:
                        start = 0
                    else:                    
                        start = int(elements_per_profile[:profile_index].sum())
                        
                    stop  = start + int(elements_per_profile[j, profile_index])
                    
                    sample_indices = slice(start, stop)
                    
                    u_indices = (slice(i, i+1),
                                 slice(j, j+1), 
                                 slice(0, sample_indices.stop - sample_indices.start))
                    
                    uarray[u_indices] = array[sample_indices]
        #--- End: if

        return uarray[indices]
    #--- End: def

    @property
    def ndim(self):
        return self._ndim

    @property
    def shape(self):
        return self._shape

    @property
    def size(self):
        return self._size

    @property
    def dtype(self):
        return self.array.dtype

    @property
    def isunique(self):
        '''
        '''
        return sys.getrefcount(self.array) <= 2
    
    def open(self):
        self.array.open()

    def close(self):
        self.array.close()
#--- End: class