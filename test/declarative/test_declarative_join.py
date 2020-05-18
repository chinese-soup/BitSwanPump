import os

import bspump.declarative
import bspump.unittest


class TestDeclarativeJoin(bspump.unittest.TestCase):

	def setUp(self) -> None:
		super().setUp()
		self.Builder = bspump.declarative.ExpressionBuilder(self.App)


	def load(self, decl_fname):
		basedir = os.path.dirname(__file__)
		with open(os.path.join(basedir, decl_fname), 'r') as f:
			return self.Builder.parse(f.read())


	def test_join_01(self):
		event = {
			'string': "STRING",
			'integer': 15,
		}

		decl = self.load('./test_join_01.yaml')

		res = decl({}, event)
		self.assertEqual(res, "STRING:15:None")


	def test_add_01(self):
		event = {
			'string1': "STRING1",
			'string2': "STRING2",
		}

		decl = self.load('./test_add_01.yaml')

		res = decl({}, event)
		self.assertEqual(res, "STRING1:STRING2")