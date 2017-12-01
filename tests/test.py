#!/usr/bin/env python

import os
import os.path
import tempfile
import subprocess
import time
import signal
import re
import sys
import shutil
import decode_out as dec
import csv
import abc

#file_locations = os.path.expanduser(os.getcwd())
file_locations = '.'
#logisim_location = os.path.join(os.getcwd(),"logisim.jar")
logisim_location = "logisim.jar"


class TestCase():
  """
      Runs specified circuit file and compares output against the provided reference trace file.
  """

  def __init__(self, circfile, expected):
    self.circfile  = circfile
    self.expected = expected

  def __call__(self, typ):
    oformat = dec.get_test_format(typ)
    if not oformat:
        print "CANNOT format test type"
        return (False, "Error in the test")

    try:
        if not isinstance(self.expected, list):
            # it is a file so parse it
            self.expected = [x for x in ReferenceFileParser(oformat, self.expected).outputs()]
        else:
            [oformat.validate(x) for x in self.expected]
    except dec.OutputFormatException as e:
        print "Error in formatting of expected output:"
        print "\t", e
        return (False, "Error in the test")

    output = tempfile.TemporaryFile(mode='r+')
    command = ["java","-jar",logisim_location,"-tty","table", self.circfile]
    proc = subprocess.Popen(command,
                            stdin=open(os.devnull),
                            stdout=subprocess.PIPE)
    try:
      debug_buffer = [] 
      passed = compare_unbounded(proc.stdout,self.expected, oformat, debug_buffer)
    except dec.OutputFormatException as e:
        print "Error in formatting of Logisim output:"
        print "\t", e
        return (False, "Error in the test")
    finally:
      if os.name != 'nt':
        os.kill(proc.pid,signal.SIGTERM)
    if passed:
      return (True, "Matched expected output")
    else:
      print "Format is student then expected"
      wtr = csv.writer(sys.stdout, delimiter='\t')
      oformat.header(wtr)
      for row in debug_buffer:
        wtr.writerow(['{0:x}'.format(b) for b in row[0]])
        wtr.writerow(['{0:x}'.format(b) for b in row[1]])

      return (False, "Did not match expected output")

def compare_unbounded(student_out, expected, oformat, debug):
  parser = OutputProvider(oformat)
  for i in range(0, len(expected)):
    line1 = student_out.readline()
    values_student_parsed = parser.parse_line(line1.rstrip())

    debug.append((values_student_parsed, expected[i]))

    if values_student_parsed != expected[i]:
      return False

  return True

def run_tests(tests):
  # actual submission testing code
  print "Testing files..."
  tests_passed = 0
  tests_failed = 0

  for description,test,typ in tests:
    test_passed, reason = test(typ)
    if test_passed:
      print "\tPASSED test: %s" % description
      tests_passed += 1
    else:
      print "\tFAILED test: %s (%s)" % (description, reason)
      tests_failed += 1
  
  print "Passed %d/%d tests" % (tests_passed, (tests_passed + tests_failed))

class OutputProvider(object):
    def __init__(self, format):
        self.format = format

    @abc.abstractmethod
    def outputs(self):
        pass
    
    def parse_line(self, line):
        value_strs = line.split('\t')   
        values_bin = [''.join(v.split(' ')) for v in value_strs] 
        try:
            values = [int(v, 2) for v in values_bin]
        except ValueError as e:
            raise dec.OutputFormatException("non-integer in {}".format(values_bin))
        self.format.validate(values)
        return values

class ReferenceFileParser(OutputProvider):
    def __init__(self, format, filename=None):
        self.f = filename
        super(ReferenceFileParser, self).__init__(format)

    def outputs(self):
        assert self.f is not None, "cannot use outputs if no filename given"
        with open(self.f, 'r') as inp:
            for line in inp.readlines():
                values = self.parse_line(line)
                yield values 

p1_tests = [
  ("ALU add (with overflow) test, with output in python",
        TestCase(os.path.join(file_locations,'alu-add.circ'),
                 [[0, 0, 0, 0x7659035D],
                  [1, 1, 0, 0x87A08D79],
                  [2, 1, 0, 0x80000000],
                  [3, 0, 1, 0x00000000],
                  [4, 0, 0, 0x00000000],
                  [5, 0, 0, 0x00000227],
                  [6, 1, 0, 0x70000203],
                  [7, 0, 0, 0xFFFFFEFF],
                  [8, 0, 1, 0x00000000],
                  [9, 0, 1, 0x00000000],
                  [10, 0, 1, 0x00000000],
                  [11, 0, 1, 0x00000000],
                  [12, 0, 1, 0x00000000],
                  [13, 0, 1, 0x00000000],
                  [14, 0, 1, 0x00000000],
                  [15, 0, 1, 0x00000000]]), "alu"),
  ("ALU add (with overflow) test",
        TestCase(os.path.join(file_locations,'alu-add.circ'),
                 os.path.join(file_locations,'reference_output/alu-add.out')), "alu"),
  ("ALU arithmetic right shift test",
        TestCase(os.path.join(file_locations,'alu-sra.circ'),
                 os.path.join(file_locations,'reference_output/alu-sra.out')), "alu"),
  ("RegFile read/write test",
        TestCase(os.path.join(file_locations,'regfile-read_write.circ'),
                 os.path.join(file_locations,'reference_output/regfile-read_write.out')), "regfile"),
  ("RegFile $zero test",
        TestCase(os.path.join(file_locations,'regfile-zero.circ'),
                 os.path.join(file_locations,'reference_output/regfile-zero.out')), "regfile"),
]

# 2 stage pipeline tests
p2_tests = [
  ("CPU starter test",
        TestCase(os.path.join(file_locations,'CPU-starter_kit_test.circ'),
                 os.path.join(file_locations,'reference_output/CPU-starter_kit_test.out')), "cpu"),
]

# Single-cycle (sc) tests
p2sc_tests = [
  ("CPU starter test",
        TestCase(os.path.join(file_locations,'CPU-starter_kit_test.circ'),
                 os.path.join(file_locations,'reference_output/CPU-starter_kit_test.sc.out')), "cpu"),
  ("func test",
        TestCase(os.path.join(file_locations,'func_test.circ'),
        [
                         [0,0,0,0],
                         [36,0,0,0],
                         [36,16,0,0]
                         ]), "cpu-end")
]

if __name__ == '__main__':
  if len(sys.argv) < 2:
    print("Usage: " + sys.argv[0] + " (p1|p2|p2sc)")
    sys.exit(-1)
  if sys.argv[1] == 'p1':
    run_tests(p1_tests)
  elif sys.argv[1] == 'p2':
    run_tests(p2_tests)
  elif sys.argv[1] == 'p2sc':
    run_tests(p2sc_tests)
  else:
    print("Usage: " + sys.argv[0] + " (p1|p2)")
    sys.exit(-1)