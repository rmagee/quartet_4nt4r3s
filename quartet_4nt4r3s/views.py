import logging
import requests
import uuid
from django.conf import settings
from django.contrib.auth import authenticate
from django.template import loader
from io import BytesIO
from lxml import etree
from requests.auth import HTTPBasicAuth
from rest_framework import status
from rest_framework import views
from rest_framework.negotiation import DefaultContentNegotiation
from rest_framework.response import Response
from rest_framework import exceptions

from list_based_flavorpack.models import ProcessingParameters
from quartet_capture.models import Filter
from quartet_capture.tasks import create_and_queue_task, get_rules_by_filter
from serialbox.models import Pool

logger = logging.getLogger(__name__)


class DefaultXMLContent(DefaultContentNegotiation):

    def select_renderer(self, request, renderers, format_suffix):
        """
        Use the XML renderer as default.
        """
        # Allow URL style format override.  eg. "?format=json
        format_query_param = self.settings.URL_FORMAT_OVERRIDE
        format = format_suffix or request.query_params.get(format_query_param)
        request.query_params.get(format_query_param)
        header = request.META.get('HTTP_ACCEPT', '*/*')
        if format is None and header == '*/*':
            for renderer in renderers:
                if renderer.media_type == "application/xml":
                    return (renderer, renderer.media_type)
        return DefaultContentNegotiation.select_renderer(self, request,
                                                         renderers, format)


class AntaresAPI(views.APIView):
    """
    Base class everything Antares.
    """
    permission_classes = []

    content_negotiation_class = DefaultXMLContent

    def get_tag_text(self, root, match_string):
        try:
            return root.find(match_string).text
        except AttributeError:
            raise
        except:
            return None

    def auth_user(self, username, password):
        """
        Authenticate user.
        """
        user = authenticate(username=username, password=password)
        if user:
            return user
        else:
            return None


class AntaresNumberRequest(AntaresAPI):
    """
    Mimics:
    /rfxcelwss/services/ISerializationServiceSoapHttpPort
    Pool will be found using the itemId value:
    <ns:itemId qlfr="GTIN">[SOME.GTIN.OR.SSCC.HERE]</ns:itemId>
    if a list_based_region processing parameter with key 'item_value' and 'item_id' value is found,
    its associated pool will be used.
    Example:
    ProcessingParameter: {key: "item_value",
                          value: "10342195308095"}
    would be a match for:
    <ns:itemId qlfr="GTIN">10342195308095</ns:itemId>

    If none is found, then the itemId value is matched against the pool.machine_name.
    For instance a pool.machine_name equal to 10342195308095 would be matched if the itemId in the inbound xml
    is the following:
     <ns:itemId qlfr="GTIN">10342195308095</ns:itemId>
    """

    def post(self, request, format=None):
        try:
            root = etree.iterparse(BytesIO(request.body), events=('end',),
                                   remove_comments=True)
            parsed_data = self.parse_root(root)
            username = parsed_data.get('username')
            password = parsed_data.get('password')
            scheme = getattr(settings, 'ANTARES_SERIALBOX_SCHEME', request.scheme)
            host = getattr(settings, 'ANTARES_SERIALBOX_HOST', '127.0.0.1')
            port = getattr(settings, 'ANTARES_SERIALBOX_PORT', None)
            logger.debug('Using scheme, host, port %s, %s, %s', scheme, host, port)
            id_count = parsed_data.get('count')

            if parsed_data.get('is_gtin'):
                item_id = parsed_data.get('item_id')
            elif parsed_data.get('is_sscc'):
                item_id = '{0}{1}'.format(parsed_data.get('extension_digit'),parsed_data.get('company_prefix'))

            pool = self.match_item_with_pool_machine_name(item_id)
            if not pool:
                # match region/pool with item_id.
                pool = self.match_item_with_param(item_id)
            event_id = parsed_data.get('event_id')
            payload = {'format': 'xml', 'eventId': event_id, 'requestId': event_id}
            if not port:
                url = "%s://%s/serialbox/allocate/%s/%d/?format=xml" % (
                    scheme, host, pool.machine_name, int(id_count))
            else:
                url = "%s://%s:%s/serialbox/allocate/%s/%d/?format=xml" % (
                    scheme, host, port, pool.machine_name, int(id_count))
            api_response = requests.get(url, params=payload,
                                        auth=HTTPBasicAuth(username, password),
                                        verify=False)
            logger.debug(api_response)
            ret = Response(api_response.text, api_response.status_code)
        except Pool.DoesNotExist as pdn:
            raise exceptions.NotFound(str(pdn))
        except Exception as e:
            raise exceptions.APIException(str(e), status.HTTP_500_INTERNAL_SERVER_ERROR)

        return ret

    def parse_root(self, root):
        parsed_data = {'is_gtin': False, 'is_sscc': False}
        for event, element in root:
            print(element.tag)
            if element.tag.endswith('Username'):
                parsed_data['username'] = getattr(element, 'text', '').strip()
            elif 'Password' in element.tag:
                parsed_data['password'] = getattr(element, 'text', '').strip()
            elif 'itemId' in element.tag:
                if element.attrib.get('qlfr') == 'GTIN':
                    parsed_data['item_id'] = getattr(element, 'text', '').strip()
                    parsed_data['is_gtin'] = True
            elif 'allocOrgId' in element.tag:
                if element.attrib.get('qlfr') == 'GS1_COMPANY_PREFIX':
                    parsed_data['company_prefix'] = getattr(element, 'text', '').strip()
            elif element.tag.endswith('val'):
                name = element.attrib.get('name')
                if name == 'SSCC_EXT_DIGIT':
                    parsed_data['extension_digit'] = getattr(element, 'text', '').strip()
                    parsed_data['is_sscc'] = True
            elif element.tag.endswith('idCount'):
                parsed_data['count'] = getattr(element, 'text', '').strip()
            elif element.tag.endswith('syncAllocateTraceIds'):
                parsed_data['request_id'] = element.attrib.get('requestId')
            elif element.tag.endswith('eventId'):
                parsed_data['event_id'] = getattr(element, 'text', '').strip()
        return parsed_data

    def parse_header(self, header):
        print('parse_header called')

    def parse_body(self, body):
        print('parse_body called')

    def match_item_with_param(self, item_id):
        try:
            return ProcessingParameters.objects.get(key="item_value",
                                                    value=item_id).list_based_region.pool
        except:
            return None

    def match_item_with_pool_machine_name(self, item_id):
        return Pool.objects.get(machine_name=item_id)


class AntaresEPCISReport(AntaresAPI):
    """
    Mimics /rfxcelwss/services/IMessagingServiceSoapHttpPort
    Takes in a SOAP request with an EPCIS report,
    tosses away the SOAP piece and saves the EPCIS document to a file,
    also kicks off a rule.
    """

    def post(self, request, format=None):
        # get the message from the request
        root = etree.fromstring(request.body)
        header = root.find('{http://schemas.xmlsoap.org/soap/envelope/}Header')
        body = root.find('{http://schemas.xmlsoap.org/soap/envelope/}Body')
        username = self.get_tag_text(header,
                                     './/{http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd}Username')
        password = self.get_tag_text(header,
                                     './/{http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd}Password')
        user = self.auth_user(username=username, password=password)
        if user:
            data = {"uuid_msg_id": uuid.uuid1(),
                    "created_date_time": "2018-10-10"}
            template = loader.get_template("soap/received.xml")
            xml = template.render(data)
            run_immediately = request.query_params.get('run-immediately',
                                                       False)
            self.trigger_epcis_task(body, user, run_immediately)
            return Response(xml, status=status.HTTP_200_OK)
        else:
            template = loader.get_template("soap/unauthorized.xml")
            xml = template.render({})
            return Response(xml, status=status.HTTP_401_UNAUTHORIZED)

    def trigger_epcis_task(self, soap_body, user, run_immediately=False):
        """
        Triggers an EPCIS rule task using the EPCISDocument.
        """
        epcis_document = etree.tostring(
            soap_body.find('.//{urn:epcglobal:epcis:xsd:1}EPCISDocument'))
        if isinstance(epcis_document, bytes):
            epcis_document = epcis_document.decode('utf-8')
        try:
            default_filter = getattr(settings, 'DEFAULT_ANTARES_FILTER',
                                     'Antares')
            logger.info('Default antares filter is %s', default_filter)
            rules = get_rules_by_filter(default_filter, epcis_document)
            logger.info('Rules in filter: %', rules)
        except Filter.DoesNotExist:
            rules = [getattr(settings, 'DEFAULT_ANTARES_RULE', 'EPCIS')]
            logger.debug('No filter could be found using rule %s.', rules)

        for rule in rules:
            create_and_queue_task(data=epcis_document,
                                  rule_name=rule,
                                  task_type="Input",
                                  run_immediately=run_immediately,
                                  initial_status="WAITING",
                                  task_parameters=[],
                                  user_id=user.id)
