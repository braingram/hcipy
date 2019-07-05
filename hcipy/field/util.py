import numpy as np
from .coordinates import RegularCoords, SeparatedCoords, UnstructuredCoords
from .field import Field
from .cartesian_grid import CartesianGrid

import itertools

def make_uniform_grid(dims, extent, center=0, has_center=False):
	'''Create a uniformly-spaced :class:`Grid` of a certain shape and size.

	Parameters
	----------
	dims : scalar or ndarray
		The number of points in each dimension. If this is a scalar, it will
		be multiplexed over all dimensions.
	extent : scalar or ndarray
		The total extent of the grid in each dimension.
	center : scalar or ndarray
		The center point. The grid will by symmetric around this point.
	has_center : boolean
		Does the grid has to have the center as one of its points. If this is
		False, this does not mean that the grid will not have the center.

	Returns
	-------
	Grid
		A :class:`Grid` with :class:`RegularCoords`.
	'''

	num_dims = max(np.array([dims]).shape[-1], np.array([extent]).shape[-1], np.array([center]).shape[-1])

	dims = (np.ones(num_dims) * dims).astype('int')
	extent = (np.ones(num_dims) * extent).astype('float')
	center = (np.ones(num_dims) * center).astype('float')

	delta = extent / dims
	zero = -extent / 2 + center + delta / 2

	if has_center:
		zero -= delta / 2 * (1 - np.mod(dims, 2))

	return CartesianGrid(RegularCoords(delta, dims, zero))

def make_pupil_grid(dims, diameter=1):
	'''Makes a new :class:`Grid`, meant for descretisation of a pupil-plane wavefront.

	This grid is symmetric around the origin, and therefore has no point exactly on
	the origin for an even number of pixels.

	Parameters
	----------
	dims : ndarray or integer
		The number of pixels per dimension. If this is an integer, this number
		of pixels is used for all dimensions.
	diameter : ndarray or scalar
		The diameter of the grid in each dimension. If this is a scalar, this diameter
		is used for all dimensions.
	
	Returns
	-------
	Grid
		A :class:`CartesianGrid` with :class:`RegularCoords`.
	'''
	diameter = (np.ones(2) * diameter).astype('float')
	dims = (np.ones(2) * dims).astype('int')

	delta = diameter / (dims - 1)
	zero = -diameter / 2

	return CartesianGrid(RegularCoords(delta, dims, zero))

def make_focal_grid(pupil_grid, q=1, num_airy=None, focal_length=1, wavelength=1):
	from ..fourier import make_fft_grid

	f_lambda = focal_length * wavelength
	if num_airy is None:
		fov = 1
	else:
		fov = (num_airy * np.ones(pupil_grid.ndim, dtype='float')) / (pupil_grid.shape / 2)
	
	if np.max(fov) > 1:
		import warnings
		warnings.warn('Focal grid is larger than the maximum allowed angle (fov=%.03f). You may see wrapping when doing propagations.' % np.max(fov), stacklevel=2)
		
	uv = make_fft_grid(pupil_grid, q, fov)
	focal_grid = uv.scaled(f_lambda / (2*np.pi))
	
	return focal_grid

def make_hexagonal_grid(circum_diameter, n_rings, pointy_top=False, center=None):
	'''Make a regular hexagonal grid.

	Parameters
	----------
	circum_diameter : scalar
		The circum diameter of the hexagons in the grid.
	n_rings : integer
		The number of rings in the grid.
	pointy_top : boolean
		If the hexagons contained in the grid.
	center : ndarray
		The center of the grid in cartesian coordinates.
	
	Returns
	-------
	Grid
		A :class:`CartesianGrid` with `UnstructuredCoords`, indicating the 
		center of the hexagons.
	'''
	if center is None:
		center = np.zeros(2)
	
	apothem = circum_diameter * np.sqrt(3) / 4

	q = [0]
	r = [0]
	
	for n in range(1,n_rings+1):
		#top
		q += list(range(n,0,-1))
		r += list(range(0,n))
		# right top
		q += list(range(0,-n,-1))
		r += [n] * n
		# right bottom
		q += [-n] * n
		r += list(range(n,0,-1))
		# bottom
		q += list(range(-n,0))
		r += list(range(0,-n,-1))
		# left bottom
		q += list(range(0,n))
		r += [-n] * n
		# left top
		q += [n] * n
		r += list(range(-n,0))
	
	x = (-np.array(q) + np.array(r)) * circum_diameter / 2 + center[0]
	y = (np.array(q) + np.array(r)) * apothem * 2 + center[1]

	weight = 2 * apothem**2 * np.sqrt(3)

	if pointy_top:
		return CartesianGrid(UnstructuredCoords((x, y)), weight)
	else:
		return CartesianGrid(UnstructuredCoords((y, x)), weight)

def make_chebyshev_grid(dims, minimum=None, maximum=None):
	if minimum is None:
		minimum = -1
	
	if maximum is None:
		maximum = 1
	
	dims = np.array(dims)
	minimum = np.ones(len(dims)) * minimum
	maximum = np.ones(len(dims)) * maximum

	middles = (minimum + maximum) / 2
	intervals = (maximum - minimum) / 2

	sep_coords = []
	for dim, middle, interval in zip(dims, middles, intervals):
		c = np.cos(np.pi * (2 * np.arange(dim) + 1) / (2.0 * dim))
		c = middle + interval * c
		sep_coords.append(c)
	
	return CartesianGrid(SeparatedCoords(sep_coords))

def make_supersampled_grid(grid, oversampling):
	'''Make a new grid that oversamples by a factor `oversampling`.

	.. note ::
		The Grid `grid` must be a grid with separable coordinates.

	Parameters
	----------
	grid : Grid
		The grid that we want to oversample.
	oversampling : integer or scalar or ndarray
		The factor by which to oversample. If this is a scalar, it will be rounded to
		the nearest integer. If this is an array, a different oversampling factor will
		be used for each dimension.
	
	Returns
	-------
	Grid
		The oversampled grid.
	'''
	oversampling = (np.round(oversampling)).astype('int')

	if grid.is_regular:
		delta_new = grid.delta / oversampling
		zero_new = grid.zero - grid.delta / 2 + delta_new / 2
		dims_new = grid.dims * oversampling

		return grid.__class__(RegularCoords(delta_new, dims_new, zero_new))
	elif grid.is_separated:
		raise NotImplementedError()
	
	raise ValueError('Cannot create a supersampled grid from a non-separated grid.')

def make_subsampled_grid(grid, undersampling):
	'''Make a new grid that undersamples by a factor `undersampling`.

	.. note ::
		The dimensions of the `grid` must be divisible by `undersampling`.

	Parameters
	----------
	grid : Grid
		The grid that we want to oversample.
	undersampling : integer or scalar or ndarray
		The factor by which to undersample. If this is a scalar, it will be rounded to
		the nearest integer. If this is an array, a different undersampling factor will
		be used for each dimension.
	
	Returns
	-------
	Grid
		The undersampled grid.
	'''
	undersampling = (np.round(undersampling)).astype('int')

	if grid.is_regular:
		delta_new = grid.delta * undersampling
		zero_new = grid.zero - grid.delta / 2 + delta_new / 2
		dims_new = grid.dims // undersampling

		return grid.__class__(RegularCoords(delta_new, dims_new, zero_new))
	elif grid.is_separated:
		raise NotImplementedError()
	
	raise ValueError("Cannot create a subsampled grid from a non-separated grid.")

def subsample_field(field, subsampling, new_grid=None, statistic='mean'):
	'''Average the field over subsampling pixels in each dimension.

	.. note ::
		The dimensions of the grid of `field` must be divisible by `subsampling`.

	Parameters
	----------
	field : Field
		The field to subsample. The grid of this field must have the right
		dimensions to be able to be subsampled.
	subsampling : integer or scalar or ndarray
		The subsampling factor. If this is a scalar, it will be rounded to the 
		nearest integer. If this is an array, the subsampling factor will be 
		different for each dimension.
	new_grid : Grid
		If this grid is given, no new grid will be calculated and this grid will
		be used instead. This saves on calculation time if your new grid is already
		known beforehand.
	statistic : string or callable
		The statistic to compute (default is 'mean').
		The following statistics are available:
		  * 'mean' : compute the mean of values for points within each superpixel.
		  * 'median' : compute the median of values for points within each superpixel.
		  * 'sum' : compute the sum of values for points within each  superpixel. 
		    This is identical to a weighted histogram.
		  * 'min' : compute the minimum of values for points within each superpixel.
		  * 'max' : compute the maximum of values for point within each superpixel.

	Returns
	-------
	Field
		The subsampled field.
	'''
	subsampling = (np.round(subsampling)).astype('int')

	if new_grid is None:
		new_grid = make_subsampled_grid(field.grid, subsampling)
	
	reshape = []
	axes = []
	for i, s in enumerate(new_grid.shape):
		reshape.extend([s, subsampling])
		axes.append(2 * i + 1)
	
	if field.tensor_order > 0:
		reshape = list(field.tensor_shape) + reshape
		axes = np.array(axes) + field.tensor_order
		new_shape = list(field.tensor_shape) + [-1]
	else:
		new_shape = [-1]

	available_statistics = {
		'mean': np.mean,
		'median': np.median,
		'max': np.max,
		'min': np.min,
		'sum': np.sum
	}

	if statistic not in available_statistics:
		raise ValueError('This statistic is not recognized.')
	
	if field.grid.is_regular:
		# All weights will be the same, so the array can be combined without taking the weights into account.
		return Field(available_statistics[statistic](field.reshape(tuple(reshape)), axis=tuple(axes)).reshape(tuple(new_shape)), new_grid)
	else:
		# Some weights will be different so calculate weighted mean instead.
		if statistic in ['min', 'max']:
			f = available_statistics[statistic](field.reshape(tuple(reshape)), axis=tuple(axes))
			return Field(f.reshape(tuple(new_shape)), new_grid)
		elif statistic in ['sum', 'mean']:
			weights = field.grid.weights
			w = weights.reshape(tuple(reshape)).sum(axis=tuple(axes))
			f = available_statistics[statistic]((field*weights).reshape(tuple(reshape)), axis=tuple(axes))
			return Field((f / w).reshape(tuple(new_shape)), new_grid)
		else:
			raise NotImplementedError('The median statistic is not implemented for non-regular grids.')

def evaluate_supersampled(field_generator, grid, oversampling, statistic='mean', make_sparse=True):
	'''Evaluate a Field generator on `grid`, with an oversampling.

	Parameters
	----------
	field_generator : Field generator or list of Field generators
		The field generator to evaluate. If this is a list of Field generators,
		each Field generator will be evaluated and stored in a ModeBasis.
	grid : Grid
		The grid on which to evaluate `field_generator`.
	oversampling : integer or scalar or ndarray
		The factor by which to oversample. If this is a scalar, it will be rounded to
		the nearest integer. If this is an array, a different oversampling factor will
		be used for each dimension.
	statistic : string or callable
		The statistic to compute (default is 'mean').
		The following statistics are available:
		  * 'mean' : compute the mean of values for points within each superpixel.
		  * 'median' : compute the median of values for points within each superpixel.
		  * 'sum' : compute the sum of values for points within each  superpixel. 
		    This is identical to a weighted histogram.
		  * 'min' : compute the minimum of values for points within each superpixel.
		  * 'max' : compute the maximum of values for point within each superpixel.
	make_sparse : boolean
		If the resulting ModeBasis needs to be sparsified. This is ignored if
		only a single Field generator is provided.

	Returns
	-------
	Field or ModeBasis
		The evaluated field or mode basis.
	'''
	import scipy.sparse
	from ..mode_basis import ModeBasis

	if isinstance(field_generator, (list, tuple)):
		modes = []

		for fg in field_generator:
			field = evaluate_supersampled(fg, grid, oversampling, statistic)

			if make_sparse:
				field = scipy.sparse.csr_matrix(field)
				field.eliminate_zeros()
			
			modes.append(field)
		
		return ModeBasis(modes, grid)
	
	new_grid = make_supersampled_grid(grid, oversampling)
	
	if grid.is_separated:
		# Use sub grids to evaluate field generator. This avoids a huge memory usage 
		# for large oversamplings. New grid is guaranteed to be able to be split up into
		# oversampling^ndim parts. Each of these evaluations uses the same amount of
		# memory as the final grid.
		field = Field(np.empty(grid.size), grid)

		for part in itertools.product(range(oversampling), repeat=grid.ndim):
			sub_new_coords = []
			sub_coords = []
			mask = np.ones(grid.shape, dtype='bool')

			# Create a sub grid and a mask on the original array where the subarray is located.
			for i, (p, s) in enumerate(zip(part, grid.dims)):
				print(p*s, new_grid.separated_coords[i].size)
				sub_new_coords.append(new_grid.separated_coords[i][p*s:(p+1)*s])
				sub_coords.append(grid.separated_coords[i][p*s//oversampling:(p+1)*s//oversampling])

				# Mask out the parts outside of the current subgrid
				slices = [slice(None)] * grid.ndim
				slices[grid.ndim - i - 1] = slice(0, p * s // oversampling)
				mask[tuple(slices)] = False
				slices[grid.ndim - i - 1] = slice((p + 1) * s // oversampling, None)
				mask[tuple(slices)] = False

			# Create sub grids.
			sub_new_grid = new_grid.__class__(SeparatedCoords(sub_new_coords))
			sub_grid = grid.__class__(SeparatedCoords(sub_coords))

			# Evaluate sub field
			sub_new_field = field_generator(sub_new_grid)
			sub_field = subsample_field(sub_new_field, oversampling, sub_grid, statistic)

			# Insert sub field into final field at the correct pixels.
			field[mask.ravel()] = sub_field

		return field
	else:
		# Cannot use sub grids, so fall back to evaluation of generator on the full 
		# supersampled grid.
		field = field_generator(new_grid)
		return subsample_field(field, oversampling, grid, statistic)

def make_uniform_vector_field(field, jones_vector):
	'''Make an uniform vector field from a scalar field and a jones vector.
	
	Parameters
	----------
	field : Field
		An input scalar field that is expanded to a vector field
	jones_vector : array_like
		The output vector at every pixel

	Returns
	-------
	Field
		The expanded vector field
	'''
	if field.is_scalar_field():
		return Field([ei * field for ei in jones_vector], field.grid)

def make_uniform_vector_field_generator(field_generator, jones_vector):
	'''Make an uniform vector field generator from a scalar field generator and a jones vector.
	
	Parameters
	----------
	field_generator : Field generator
		The field generator to evaluate.
	jones_vector : array_like
		The output vector at every grid coordinate

	Returns
	-------
	Field generator
		This function can be evaluated on a grid to get a Field.
	'''
	
	def func(grid):
		scalar_field = field_generator(grid)
		return Field([ei * scalar_field for ei in jones_vector], grid)

	return func
