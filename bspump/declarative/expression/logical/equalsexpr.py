import functools

from ...abc import SequenceExpression


class EQUALS(SequenceExpression):
	"""
	Checks if all expressions are equal
	"""

	def __call__(self, context, event, *args, **kwargs):
		return functools.reduce(
			lambda x, y: self.evaluate(x, context, event, *args, **kwargs) == self.evaluate(y, context, event, *args, **kwargs),
			self.Items
		)
