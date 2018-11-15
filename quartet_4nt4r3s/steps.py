import io

from django.core.files.base import File

from quartet_epcis.parsing.steps import EPCISParsingStep as EPS
from quartet_capture.rules import RuleContext
from quartet_epcis.parsing.parser import QuartetParser
from quartet_4nt4r3s.conversion import AntaresBarcodeConverter
from quartet_4nt4r3s.parser import BusinessEPCISParser


class EPCISParsingStep(EPS):
    def execute(self, data, rule_context: RuleContext):
        parser_type = QuartetParser if self.loose_enforcement else BusinessEPCISParser
        self.info('Loose Enforcement of busines rules set to %s',
                  self.loose_enforcement)
        self.info('Parsing message %s.dat', rule_context.task_name)
        try:
            if isinstance(data, File):
                parser = parser_type(data)
            else:
                parser = parser_type(io.BytesIO(data))
        except TypeError:
            try:
                parser = parser_type(io.BytesIO(data.encode()))
            except AttributeError:
                self.error("Could not convert the data into a format that "
                           "could be handled.")
                raise
        parser.parse()
        self.info('Parsing complete.')


class AntaresBarcodeConversionStep(ListBarcodeConversionStep):
    '''
    Allows the return of the extension digit along with serial number field.
    '''
    def convert(self, data):
        """
        Will convert the data parameter to a urn value and return.
        Override this to return a different value from the BarcodeConverter.
        :param data: The barcode value to convert.
        :return: An EPC URN based on the inbound data.
        """
        prop_val = AntaresBarcodeConverter(
            data,
            self.company_prefix_length,
            self.serial_number_length
        ).__getattribute__(self.prop_name)
        return prop_val if isinstance(prop_val, str) else prop_val()    
