import numpy
from numpy.linalg import LinAlgError

import cupy
from cupy.cuda import cublas
from cupy.cuda import cusolver_enabled
from cupy.cuda import device

if cusolver_enabled:
    from cupy.cuda import cusolver


def cholesky(a):
    '''Cholesky decomposition.

    Decompose a given two-dimensional square matrix into `L * L.T`,
    where `L` is a lower-triangular matrix and `.T` is a conjugate transpose
    operator. Note that in the current implementation `a` must be a real
    matrix, and only float32 and float64 are supported.

    Args:
        a (cupy.ndarray): The input matrix with dimension `(N, N)`

    .. seealso:: :func:`numpy.linalg.cholesky`
    '''
    if not cusolver_enabled:
        raise RuntimeError('Current cupy only supports cusolver in CUDA 8.0')

    # TODO(Saito): Current implementation only accepts two-dimensional arrays
    _assertCupyArray(a)
    _assertRank2(a)
    _assertNdSquareness(a)

    ret_dtype = a.dtype.char
    # Cast to float32 or float64
    if ret_dtype == 'f' or ret_dtype == 'd':
        dtype = ret_dtype
    else:
        dtype = numpy.find_common_type((ret_dtype, 'f'), ()).char

    x = a.astype(dtype, copy=True)
    n = a.shape[0]
    handle = device.get_cusolver_handle()
    devInfo = cupy.empty(1, dtype=numpy.int32)
    if x.dtype.char == 'f':
        buffersize = cusolver.spotrf_bufferSize(
            handle, cublas.CUBLAS_FILL_MODE_UPPER, n, x.data.ptr, n)
        workspace = cupy.empty(buffersize, dtype=numpy.float32)
        cusolver.spotrf(
            handle, cublas.CUBLAS_FILL_MODE_UPPER, n, x.data.ptr, n,
            workspace.data.ptr, buffersize, devInfo.data.ptr)
    else:  # a.dtype.char == 'd'
        buffersize = cusolver.dpotrf_bufferSize(
            handle, cublas.CUBLAS_FILL_MODE_UPPER, n, x.data.ptr, n)
        workspace = cupy.empty(buffersize, dtype=numpy.float64)
        cusolver.dpotrf(
            handle, cublas.CUBLAS_FILL_MODE_UPPER, n, x.data.ptr, n,
            workspace.data.ptr, buffersize, devInfo.data.ptr)
    status = int(devInfo[0])
    if status > 0:
        raise LinAlgError(
            'The leading minor of order {} '
            'is not positive definite'.format(status))
    elif status < 0:
        raise LinAlgError(
            'Parameter error (maybe caused by a bug in cupy.linalg?)')
    _tril(x, k=0)
    return x


# TODO(okuta): Implement qr


def _assertCupyArray(*arrays):
    for a in arrays:
        if not isinstance(a, cupy.core.ndarray):
            raise LinAlgError('cupy.linalg only supports cupy.core.ndarray')


def _assertRank2(*arrays):
    for a in arrays:
        if len(a.shape) != 2:
            raise LinAlgError(
                '{}-dimensional array given. Array must be '
                'two-dimensional'.format(len(a.shape)))


def _assertNdSquareness(*arrays):
    for a in arrays:
        if max(a.shape[-2:]) != min(a.shape[-2:]):
            raise LinAlgError('Last 2 dimensions of the array must be square')


def _tril(x, k=0):
    m, n = x.shape
    u = cupy.arange(m).reshape(m, 1)
    v = cupy.arange(n).reshape(1, n)
    mask = v - u <= k
    x *= mask
    return x


# TODO(okuta): Implement svd
