# -*- coding: utf-8 -*-

from error import TuttleError
from workflow_builder import WorkflowBuilder
from workflow import Workflow
from os.path import basename


class ParsingError(TuttleError):
    def __init__(self, message, line):
        self._message = message
        self._line = line
    
    def __str__(self):
        return "Parsing error on line {} : '{}'".format(self._line, self._message)
    

class WorkflowError(ParsingError):
    pass


class InvalidResourceError(ParsingError):
    pass


class InvalidProcessorError(ParsingError):
    pass


class ProjectParser():
    """Parser for tuttlefiles.
        The text describing a Workflow is called Projet
        The text describing a Process (dependencies and code)is called a section"""

    def __init__(self):
        self.wb = WorkflowBuilder()
        self.resources = {}
        self._lines = []
        self._nb_lines = 0
        self._line = ""
        self._num_line = 0
        self._eof = True
        self._filename = "_"

    def parse_and_check_file(self, filename):
        self._filename = basename(filename)
        with open(filename) as f:
            self.set_project(f.read())
        return self.parse_and_check_project()

    def parse_and_check_project(self):
        workflow = self.parse_project()
        missing = workflow.missing_inputs()
        if missing:
            error_msg = "Missing the following resources to launch the workflow :\n"
            for mis in missing:
                error_msg += "* {}\n".format(mis.url)
            # TODO : improve line reference
            raise WorkflowError(error_msg, self._nb_lines)
        unreachable = workflow.circular_references()
        if unreachable:
            error_msg = "The following resources references one another as inputs in a circular way that don't allow " \
                        "to choose which one to run first"
            for process in unreachable:
                error_msg += "* {}\n".format(process.id)
            raise WorkflowError(error_msg, self._nb_lines)
        return workflow

    def set_project(self, text):
        self._lines = text.splitlines()
        self._nb_lines = len(self._lines)
        self._num_line = 0
        self._eof = (self._nb_lines == 0)
        
    def read_line(self):
        if self._num_line < self._nb_lines:
            self._line = self._lines[self._num_line]
            self._num_line += 1
            self._eof = False
            return self._line, self._num_line, False
        else:
            self._eof = True
            self._line = ""
            return "", self._nb_lines, True

    def is_blank(self, line):
        """ Check whether the current line in a tuttlefile is blank
        """
        if len(line) > 0 and line[0] == "#":
                return True
        line_stripped = line.strip()
        return len(line_stripped) == 0
        
    def parse_dependencies_and_processor(self):
        arrow_pos = self._line.find('<-')
        if arrow_pos == -1:
            raise ParsingError("Definition of dependency expected", self._num_line)
        shebang_pos = self._line.find('#!')
        if shebang_pos == -1:
            shebang_pos = len(self._line)
            processor_name = "default"
        else:
            processor_name = self._line[shebang_pos + 2:].strip()
        process = self.wb.build_process(processor_name, self._filename, self._num_line)
        if not process:
            raise InvalidProcessorError("Invalid processor : '{}' ".format(processor_name), self._num_line)
        input_urls = self._line[arrow_pos + 2:shebang_pos].split(',')
        if len(input_urls) > 1 or input_urls[0].strip() != "":
            for input_url in input_urls:
                in_res = self.wb.get_or_build_resource(input_url.strip(), self.resources)
                if in_res is None:
                    raise InvalidResourceError("Invalid resource url : '{}' in inputs".format(input_url.strip()), self._num_line)
                process.add_input(in_res)
        outputs_urls = self._line[:arrow_pos].split(',')
        if len(outputs_urls) > 1 or outputs_urls[0].strip() != "":
            for output_url in outputs_urls:
                out_res = self.wb.get_or_build_resource(output_url.strip(), self.resources)
                if out_res is None:
                    raise InvalidResourceError("Invalid resource url : '{}' in outputs".format(output_url.strip()), self._num_line)
                if out_res.creator_process is not None:
                    raise WorkflowError("{} has been already defined in the workflow (by processor : {})".format(output_url,
                                        process._processor.name), self._num_line)
                out_res.set_creator_process(process)
                process.add_output(out_res)
        return process

    def is_first_process_line(self):
        """ Is the current line a valid first line of a process ? All blank lines must have been skipped before
            Returns a couple (is_first_line : bool, prefix found : string)
        """
        wsp = "\t "
        i = 0
        while wsp.find(self._line[i]) >= 0:
            # Char i of self._line is a white-space
            i += 1
        if i == 0:
            # Line didn't begin by white-spaces. It's not a valid first process line
            return False, "", ""
        else:
            return True, self._line[:i], self._line[i:] + "\n"

    def parse_process_line(self, prefix):
        """ Parses the line as if it is a line of process, beginning by ::prefix::.
        Returns a couple (is_process_line, line)
        is_process_line : 
            True if it is a process line
            False if not
        line :
            The line of the process, with prefix removed"""
        if self._line.startswith(prefix):
            return True, self._line[len(prefix):] + "\n"
        elif self.is_blank(self._line):
            return True, ""
        else:
            return False, ""
    
    def parse_section(self):
        """ Parse a whole section : dependency definition + processor type + process code
        All blank lines must have been skipped before
        """
        # Dependency definition
        process = self.parse_dependencies_and_processor()
        line, num_line, eof = self.read_line()
        # Any number of blank lines
        while self.is_blank(line):
            line, num_line, eof = self.read_line()
            if eof:
                return process
        # Several lines all beginning by white-spaces define a process
        process_code = ""
        is_process_line, wsp_prefix, process_line = self.is_first_process_line()
        while is_process_line and not self._eof:
            process_code += process_line
            self.read_line()
            if self._eof:
                break
            is_process_line, process_line = self.parse_process_line(wsp_prefix)
        if process_line == "\n":
            # Remove carriage return
            process_code = process_code[:-1]
        process.set_code(process_code)
        return process

    def parse_project(self):
        """ Parse a full project describing a workflow
        """
        workflow = Workflow(self.resources)
        #workflow.resources = self.resources
        line, num_line, eof = self.read_line()
        while True:
            while self.is_blank(line):
                line, num_line, eof = self.read_line()
                if eof:
                    return workflow
            process = self.parse_section()
            workflow.add_process(process)
            if self._eof:
                return workflow
