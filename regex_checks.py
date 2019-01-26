
import re
from enum import IntEnum

class MatchControl:
	def __init__(self):
		self.match_rules = []

	def add(self, rule):
		self.match_rules.append(rule)

	def check_all(self, haystack):
		b = 0
		for m in self.match_rules:
			if m.test(haystack):
				b |= m.flag
		return b

class MatchRule:
	def __init__(self, name, flag, func):
		self.name = name
		self.flag = flag
		self.func = func

	def test(self, text):
		return self.func(text)

	def __call__(self, *args, **kwargs):
		return self.func(*args, **kwargs)

	@classmethod
	def create(cls, name, flag):
		def decorator(func):
			return cls(name=name, flag=flag, func=func)
		return decorator

class RegexHolder:
	missing_code_block = re.compile((
			r'^('
			r'@echo off *'
			r'|if (not )?errorlevel \d+ \(.*'
			r'|if (not )?defined \w+ \(.*'
			r'''|if (\/i )?(not )?["'.\w%!-]+( *== *|( +(equ|neq|lss|leq|gtr|geq) +))?["'.\w%!-]+ ?\(.*'''
			r'|goto :?\w+'
			r'|set *(\/a|\/p)? *[\"\w]+=[\"\w ]+'
			r')$'), re.I | re.M)

	inline_code_lines = re.compile(r'^ {0,3}`(.*)`[\t ]*$', re.M)
	consecutive_inline_code_lines = re.compile(r'^ {0,3}`(.*)`[\t ]*\n\n?`.*\n\n?`', re.M)

class MatchBank(IntEnum):
	missing_code_block = 1
	inline_code_misuse = 2

@MatchRule.create(
		MatchBank.missing_code_block.name,
		MatchBank.missing_code_block.value)
def missing_code_block_rule(text):
	return bool(RegexHolder.missing_code_block.search(text))

@MatchRule.create(
		MatchBank.inline_code_misuse.name,
		MatchBank.inline_code_misuse.value)
def missing_code_block_after_backtick_strip(text):
	if not RegexHolder.consecutive_inline_code_lines.search(text):
		# Avoid cases like t3_abqs9c
		return False

	new_text, n = RegexHolder.inline_code_lines.subn(r'\1', text)
	if n <= 2:
		# Ignore if it's just two lines
		return False

	return bool(RegexHolder.missing_code_block.search(new_text))

match_control = MatchControl()
match_control.add(missing_code_block_rule)
match_control.add(missing_code_block_after_backtick_strip)
