from builtins import (range, super)

import numpy

from . import abstract


class RaggedIndexedArray(abstract.CompressedArray):
    '''A container for an indexed ragged compressed array.

A collection of features stored using an indexed ragged array combines
all features along a single dimension (the "sample" dimension) such
that the values of each feature in the collection are interleaved.

The information needed to uncompress the data is stored in a separate
"index" array that specifies the feature that each element of the
sample dimension belongs to.

    '''
    def __init__(self, compressed_array=None, shape=None, size=None,
                 ndim=None, index_array=None):
        '''**Initialization**

:Parameters:

    compressed_array: subclass of `Array`
        The compressed array.

    shape: `tuple`
        The uncompressed array dimension sizes.

    size: `int`
        Number of elements in the uncompressed array.

    ndim: `int`
        The number of uncompressed array dimensions

    index_array: `Data`
        The "index" array required to uncompress the data, identical
        to the data of a CF-netCDF "index" variable.

        '''
        super().__init__(compressed_array=compressed_array,
                         shape=shape, size=size, ndim=ndim,
                         sample_axis=0,
                         compression_type='ragged indexed',
                         _index_array=index_array)
    #--- End: def

    def __getitem__(self, indices):
        '''x.__getitem__(indices) <==> x[indices]

Returns an subspace of the uncompressed data an independent numpy
array.

The indices that define the subspace are relative to the uncompressed
data and must be either `Ellipsis` or a sequence that contains an
index for each dimension. In the latter case, each dimension's index
must either be a `slice` object or a sequence of two or more integers.

Indexing is similar to numpy indexing. The only difference to numpy
indexing (given the restrictions on the type of indices allowed) is:

  * When two or more dimension's indices are sequences of integers
    then these indices work independently along each dimension
    (similar to the way vector subscripts work in Fortran).

        '''
        # ------------------------------------------------------------
        # Method: Uncompress the entire array and then subspace it
        # ------------------------------------------------------------
        
        compressed_array = self.compressed_array

        # Initialise the un-sliced uncompressed array
        uarray = numpy.ma.masked_all(self.shape, dtype=self.dtype)

        # --------------------------------------------------------
        # Compression by indexed ragged array.
        #
        # The uncompressed array has dimensions (instance
        # dimension, element dimension).
        # --------------------------------------------------------
        index_array = self.index_array.get_array()
        
        for i in range(uarray.shape[0]):
            sample_dimension_indices = numpy.where(index_array == i)[0]
            
            u_indices = (i, #slice(i, i+1),
                         slice(0, len(sample_dimension_indices)))
            
            uarray[u_indices] = compressed_array[sample_dimension_indices]
        #--- End: for

        return self.get_subspace(uarray, indices, copy=True)
    #--- End: def

    @property
    def index_array(self):
        '''
        '''
        return self._index_array
#--- End: class
