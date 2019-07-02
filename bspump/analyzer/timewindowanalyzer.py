import time
import logging

import numpy as np

import asab

from .analyzer import Analyzer
from .timewindowmatrix import TimeWindowMatrix

###

L = logging.getLogger(__name__)

###


class TimeWindowAnalyzer(Analyzer):
	'''
		This is the analyzer for events with a temporal dimension (aka timestamp).
		Configurable sliding window records events withing specified windows and implements functions to find the exact time slot.
		Timer periodically shifts the window by time window resolution, dropping previous events.

		`TimeWindowAnalyzer` operates over the `TimeWindowMatrix` object.
		`tw_dimensions` is matrix dimensions parameter as the tuple `(column_number, third_dimension)`.
		Example: `(5,1)` will create the matrix with n rows, 5 columns and 1 additional third dimension.
		`tw_format` is the letter from the table + number:

			+------------+------------------+
			| Name       | Definition       |
			+============+==================+
			| 'b'        | Byte             |
			+------------+------------------+
			| 'i'        | Signed integer   |
			+------------+------------------+
			| 'u'        | Unsigned integer |
			+------------+------------------+
			| 'f'        | Floating point   |
			+------------+------------------+
			| 'c'        | Complex floating |
			|            | point            |
			+------------+------------------+
			| 'S'        | String           |
			+------------+------------------+
			| 'U'        | Unicode string   |
			+------------+------------------+
			| 'V'        | Raw data         |
			+------------+------------------+

		Example: 'i8' stands for int64.
		`resolution`is how many seconds fit in one time cell, default value is `60`.
		`start_time` is a unix timestamp for time to start. Default value is `None`, which will be equivalent current time.
		`clock_driven` is a boolean parameter, specifying how the matrix should be advanced. If `True`, it advances on timer's tick, 
		else manually. Default value is `True`.
		`matrix_id` is an id of `TimeWindowMatrix` object alternatively passed, if not provided, the new matrix will be created with and ID derived from the Analyzer Id
		`analyze_on_clock` enables enables analyzis by timer.


		If the `TimeWindowAnalyzer` is `clock_driven`, the time should be periodically shifted (`on_clock_tick()`). The same
		function runs analyzis, if it's enabled.
	'''

	ConfigDefaults = {
		'resolution': 60, # Resolution (aka column width) in seconds
	}

	def __init__(self, app, pipeline, tw_format='f8', tw_dimensions=(15,1), resolution=60, 
				start_time=None, clock_driven=True, analyze_on_clock=False, 
				matrix_id=None, id=None, config=None):

		if clock_driven:
			analyze_period = self.Resolution / 4
		else:
			analyze_period = None
		
		super().__init__(app, pipeline, analyze_on_clock=analyze_on_clock, analyze_period=analyze_period, id=id, config=config)
		svc = app.get_service("bspump.PumpService")
		if matrix_id is None:
			matrix_id = self.Id + "Matrix"
			self.TimeWindow = TimeWindowMatrix(
				app,
				tw_dimensions=tw_dimensions,
				tw_format=tw_format,
				resolution=resolution,
				start_time=start_time, 
				id=matrix_id
			)	
			svc.add_matrix(self.TimeWindow)
		else:
			# locate
			self.TimeWindow = svc.locate_matrix(matrix_id)

		self.ClockDriven = clock_driven
		self.Resolution = resolution
		
		self.Matrix = self.TimeWindow.Matrix['time_window'] #alias
		

	def advance(self, target_ts):
		'''
			Advance time window (add columns) so it covers target `timestamp` (`target_ts`)
			Also, if `target_ts` is in top 75% of the last existing column, add a new column too.
		
		.. code-block:: python

			------------------|-----------
			target_ts  ^ >>>  |          
							  ^           
							Start         
			------------------------------

		'''

		while True:
			dt = (self.TimeWindow.Start - target_ts) / self.TimeWindow.Resolution
			if dt > 0.25: break
			self.TimeWindow.add_column()
			


	async def on_clock_tick(self):
		'''
			React on timer's tick and advance the window. And analyze.
		'''
		if self.AnalyzeOnClock:
			super().on_clock_tick()
		
		if self.ClockDriven:
			target_ts = time.time()
			self.advance(target_ts)



