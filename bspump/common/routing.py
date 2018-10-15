import logging
import asyncio
import copy
from ..abc.source import Source
from ..abc.sink import Sink
from ..abc.processor import Processor

#

L = logging.getLogger(__name__)

#

class InternalSource(Source):


	ConfigDefaults = {
		'queue_max_size': 10, # 0 means unlimited size
		'backpressure': 0.8, # Percentage of the queue that will result in a backpressure
	}


	def __init__(self, app, pipeline, id=None, config=None):
		super().__init__(app, pipeline, id=id, config=config)
		self.Loop = app.Loop 

		self.BackPressure = False
		maxsize = int(self.Config.get('queue_max_size'))
		if maxsize == 0:
			maxsize = None
			self.BackPressureLimit = None
		else:
			if maxsize == 1: maxsize = 2 # Special case
			self.BackPressureLimit = maxsize * float(self.Config.get('backpressure'))
			if self.BackPressureLimit == maxsize:
				self.BackPressureLimit -= 1
			assert(self.BackPressureLimit > 0)
		self.Queue = asyncio.Queue(maxsize=maxsize, loop=self.Loop)


	def put(self, context, event, copy_event=True):
		'''
		Context can be empty dictionary if is not provided
		'''
		if copy_event:
			event = copy.deepcopy(event)

		self.Queue.put_nowait((
			copy.deepcopy(context),
			event
		))

		if (not self.BackPressure) and (self.BackPressureLimit is not None) and (self.BackPressureLimit <= self.Queue.qsize()):
			self.BackPressure = True
			self.Pipeline.PubSub.publish("bspump.InternalSource.backpressure_on!", source=self)


	async def main(self):
		try:

			while True:
				await self.Pipeline.ready()
				context, event = await self.Queue.get()

				if (self.BackPressure) and (self.BackPressureLimit is not None) and (self.BackPressureLimit > self.Queue.qsize()):
					self.BackPressure = False
					self.Pipeline.PubSub.publish("bspump.InternalSource.backpressure_off!", source=self)

				await self.process(event, context={'ancestor':context})

		except asyncio.CancelledError:
			if self.Queue.qsize() > 0:
				L.warning("Source '{}' stopped with {} events in a queue".format(self.Id, self.Queue.qsize()))


	def rest_get(self):
		rest = super().rest_get()
		rest['Queue'] = self.Queue.qsize()
		rest['BackPressure'] = self.BackPressure
		return rest

#

class RouterMixIn(object):


	def _mixin_init(self, app):
		self.ServiceBSPump = app.get_service("bspump.PumpService")
		self.SourcesCache = {}


	def locate(self, source_id):
		source = self.ServiceBSPump.locate(source_id)
		if source is None:
			L.warning("Cannot locate '{}' in '{}'".format(source_id, self.Id))
			raise RuntimeError("Cannot locate '{}' in '{}'".format(source_id, self.Id))
		
		self.SourcesCache[source_id] = source

		source.Pipeline.PubSub.subscribe("bspump.pipeline.not_ready!", self._on_target_pipeline_ready_change)
		source.Pipeline.PubSub.subscribe("bspump.pipeline.ready!", self._on_target_pipeline_ready_change)

		# If target pipeline is not ready, throttle
		if not source.Pipeline.is_ready():
			self.Pipeline.throttle(source.Pipeline, enable=True)		

		source.Pipeline.PubSub.subscribe("bspump.InternalSource.backpressure_on!", self._on_internal_source_backpressure_ready_change)
		source.Pipeline.PubSub.subscribe("bspump.InternalSource.backpressure_off!", self._on_internal_source_backpressure_ready_change)
		if source.BackPressure:
			self.Pipeline.throttle(source, enable=True)

		return source



	def dispatch(self, context, event, source_id):
		source = self.SourcesCache.get(source_id)
		
		if source is None:
			source = self.locate(source_id)

		source.put(context, event)


	def _on_target_pipeline_ready_change(self, event_name, pipeline):
		if event_name == "bspump.pipeline.ready!":
			self.Pipeline.throttle(pipeline, enable=False)
		elif event_name == "bspump.pipeline.not_ready!":
			self.Pipeline.throttle(pipeline, enable=True)
		else:
			L.warning("Unknown event '{}' received in _on_target_pipeline_ready_change in '{}'".format(event_name, self))


	def _on_internal_source_backpressure_ready_change(self, event_name, source):
		if event_name == "bspump.InternalSource.backpressure_off!":
			self.Pipeline.throttle(source, enable=False)
		elif event_name == "bspump.InternalSource.backpressure_on!":
			self.Pipeline.throttle(source, enable=True)
		else:
			L.warning("Unknown event '{}' received in _on_internal_source_backpressure_ready_change in '{}'".format(event_name, self))


class RouterSink(Sink, RouterMixIn):

	'''
	Abstract Sink that dispatches events to other internal sources.
	One should override the process() method and call dispatch() with target source id.
	'''

	def __init__(self, app, pipeline, id=None, config=None):
		super().__init__(app, pipeline, id, config)
		self._mixin_init(app)


class RouterProcessor(Processor, RouterMixIn):

	'''
	Abstract Processor that dispatches events to other internal sources.
	One should override the process() method and call dispatch() with target source id.
	'''

	def __init__(self, app, pipeline, id=None, config=None):
		super().__init__(app, pipeline, id, config)
		self._mixin_init(app)

