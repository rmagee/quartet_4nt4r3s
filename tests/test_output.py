#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_quartet_output
------------

Tests for `quartet_output` models module.
"""
import os
from EPCPyYes.core.v1_2.events import EventType
from EPCPyYes.core.v1_2.CBV.dispositions import Disposition
from EPCPyYes.core.v1_2.CBV.business_steps import BusinessSteps
from quartet_epcis.parsing.business_parser import BusinessEPCISParser
from quartet_capture.models import Rule, Step, StepParameter, Task
from quartet_capture.tasks import execute_rule, execute_queued_task
from quartet_capture.rules import Rule as CRule
from quartet_output.steps import SimpleOutputParser, ContextKeys
from quartet_output.models import EPCISOutputCriteria
from quartet_templates.models import Template
from django.test import TestCase

from quartet_output import models

class TestQuartetOutput(TestCase):

    def test_rule_with_agg_comm_output(self):
        self._create_good_ouput_criterion()
        db_rule = self._create_rule()
        self._create_template()
        self._create_step(db_rule)
        self._create_output_steps(db_rule)
        self._create_comm_step(db_rule)
        self._create_epcpyyes_step(db_rule)
        self._create_template_step(db_rule)
        self._create_task_step(db_rule)
        db_rule2 = self._create_transport_rule()
        self._create_transport_step(db_rule2)
        db_task = self._create_task(db_rule)
        curpath = os.path.dirname(__file__)
        # prepopulate the db
        self._parse_test_data('data/antares-lot-batch.xml')
        # self._parse_test_data('data/nested_pack.xml')
        # data_path = os.path.join(curpath, 'data/ship_pallet.xml')
        with open(data_path, 'r') as data_file:
            # execute the rule
            context = execute_rule(data_file.read().encode(), db_task)
            # make suer three aggregation events were filtered out
            self.assertEqual(
                len(context.context[ContextKeys.AGGREGATION_EVENTS_KEY.value]),
                3,
                "There should be three filtered events."
            )
            # get the path to the output file
            curpath = os.path.dirname(__file__)
            outfile = os.path.join(curpath, './data/output.xml')
            # write out the results of the outbound message
            with open(outfile, 'w+') as output_file:
                output_file.write(
                    context.context[ContextKeys.OUTBOUND_EPCIS_MESSAGE_KEY.value])
                output_file.flush()


    # def test_rule_with_agg_comm_output_put(self):
    #     self._create_good_ouput_criterion()
    #     db_rule = self._create_rule()
    #     self._create_step(db_rule)
    #     self._create_output_steps(db_rule)
    #     self._create_comm_step(db_rule)
    #     self._create_epcpyyes_step(db_rule)
    #     self._create_task_step(db_rule)
    #     db_rule2 = self._create_transport_rule()
    #     self._create_transport_step(db_rule2, put_data=True)
    #     db_task = self._create_task(db_rule)
    #     curpath = os.path.dirname(__file__)
    #     # prepopulate the db
    #     self._parse_test_data('data/commission_one_event.xml')
    #     self._parse_test_data('data/nested_pack.xml')
    #     data_path = os.path.join(curpath, 'data/ship_pallet.xml')
    #     with open(data_path, 'r') as data_file:
    #         context = execute_rule(data_file.read().encode(), db_task)
    #         self.assertEqual(
    #             len(context.context[ContextKeys.AGGREGATION_EVENTS_KEY.value]),
    #             3,
    #             "There should be three filtered events."
    #         )
    #         for event in context.context[
    #             ContextKeys.AGGREGATION_EVENTS_KEY.value]:
    #             if event.parent_id in ['urn:epc:id:sgtin:305555.3555555.1',
    #                                    'urn:epc:id:sgtin:305555.3555555.2']:
    #                 self.assertEqual(len(event.child_epcs), 5)
    #             else:
    #                 self.assertEqual(len(event.child_epcs), 2)
    #         task_name = context.context[ContextKeys.CREATED_TASK_NAME_KEY]
    #         execute_queued_task(task_name=task_name)
    #         task = Task.objects.get(name=task_name)
    #         self.assertEqual(task.status, 'FINISHED')
    #
    # def test_rule_with_agg_mulit_comm(self):
    #     self._create_good_ouput_criterion()
    #     db_rule = self._create_rule()
    #     self._create_step(db_rule)
    #     self._create_output_steps(db_rule)
    #     self._create_comm_step(db_rule)
    #     self._create_epcpyyes_step(db_rule)
    #     db_task = self._create_task(db_rule)
    #     curpath = os.path.dirname(__file__)
    #     # prepopulate the db
    #     self._parse_test_data('data/commission_three_events.xml')
    #     self._parse_test_data('data/nested_pack.xml')
    #     data_path = os.path.join(curpath, 'data/ship_pallet.xml')
    #     with open(data_path, 'r') as data_file:
    #         context = execute_rule(data_file.read().encode(), db_task)
    #         self.assertEqual(
    #             len(context.context[ContextKeys.AGGREGATION_EVENTS_KEY.value]),
    #             3,
    #             "There should be three filtered events."
    #         )
    #         for event in context.context[
    #             ContextKeys.AGGREGATION_EVENTS_KEY.value]:
    #             if event.parent_id in ['urn:epc:id:sgtin:305555.3555555.1',
    #                                    'urn:epc:id:sgtin:305555.3555555.2']:
    #                 self.assertEqual(len(event.child_epcs), 5)
    #             else:
    #                 self.assertEqual(len(event.child_epcs), 2)
    #         self.assertIn(ContextKeys.OUTBOUND_EPCIS_MESSAGE_KEY.value,
    #                       context.context,
    #                       "No EPCIS message was found in the rule context.")
    #         self.assertIn(ContextKeys.OBJECT_EVENTS_KEY.value,
    #                       context.context)
    #         self.assertEqual(
    #             len(context.context[ContextKeys.OBJECT_EVENTS_KEY.value]), 3,
    #             "There should be three object events."
    #         )
    #         for oevent in context.context[
    #             ContextKeys.OBJECT_EVENTS_KEY.value]:
    #             self.assertIn(len(oevent.epc_list), [10, 2, 1],
    #                           "One of the object events in the context is "
    #                           "malformed.")

    def _create_ADD_criterion(self):
        endpoint = self._create_endpoint()
        auth = self._create_auth()
        eoc = EPCISOutputCriteria()
        # get all the events of type add
        eoc.name = "Test Criteria"
        #eoc.action = "ADD"
        eoc.read_point = 'urn:epc:id:sgln:0358716.00000.0'
        eoc.authentication_info = auth
        eoc.end_point = endpoint
        eoc.save()
        return eoc

    def _create_DELETE_criterion(self):
        endpoint = self._create_endpoint()
        auth = self._create_auth()
        eoc = EPCISOutputCriteria()
        # get all the events of type add
        eoc.name = "Test Criteria"
        eoc.action = "DELETE"
        eoc.read_point = 'urn:epc:id:sgln:0358716.00000.0'
        eoc.authentication_info = auth
        eoc.end_point = endpoint
        eoc.save()
        return eoc

    def _create_good_header_criterion(self):
        endpoint = self._create_endpoint()
        auth = self._create_auth()
        eoc = EPCISOutputCriteria()
        eoc.name = "Test Criteria"
        eoc.receiver_identifier = 'urn:epc:id:sgln:039999.111111.0'
        eoc.authentication_info = auth
        eoc.end_point = endpoint
        eoc.save()
        return eoc

    def _create_good_header_criterion(self):
        eoc = EPCISOutputCriteria()
        eoc.name = 'Test Criteria'
        eoc.receiver_identifier = 'urn:epc:id:sgln:039999.111111.0'
        eoc.end_point = self._create_endpoint()
        eoc.authentication_info = self._create_auth()
        eoc.save()
        return eoc

    def _create_endpoint(self):
        ep = models.EndPoint()
        ep.urn = 'http://testhost'
        ep.name = 'Test EndPoint'
        ep.save()
        return ep

    def _create_auth(self):
        auth = models.AuthenticationInfo()
        auth.description = 'Unit test auth.'
        auth.username = 'UnitTestUser'
        auth.password = 'UnitTestPassword'
        auth.save()
        return auth

    def _create_bad_criterion(self):
        eoc = EPCISOutputCriteria()
        eoc.name = "Test Criteria"
        eoc.action = "DELETE"
        eoc.event_type = EventType.Transaction.value
        endpoint = self._create_endpoint()
        auth = self._create_auth()
        eoc.end_point = endpoint
        eoc.authentication_info = auth
        eoc.save()
        return eoc

    def _parse_data(self, output_criteria):
        curpath = os.path.dirname(__file__)
        parser = SimpleOutputParser(
            os.path.join(curpath, 'data/epcis.xml'),
            output_criteria
        )
        parser.parse()
        parser.clear_cache()

    def _create_rule(self):
        rule = Rule()
        rule.name = 'output-test'
        rule.description = 'output test rule'
        rule.save()
        return rule

    def _create_transport_rule(self):
        rule = Rule()
        rule.name = 'Transport Rule'
        rule.description = 'Attempts to send data using transport step(s).'
        rule.save()
        return rule

    def _create_transport_step(self, rule, put_data='False'):
        step = Step()
        step.rule = rule
        step.order = 1
        step.name = 'Transport'
        step.step_class = 'quartet_output.steps.TransportStep'
        step.description = 'Sends test data.'
        step.save()
        step_parameter = StepParameter()
        step_parameter.step = step
        step_parameter.name = 'run-immediately'
        step_parameter.value = 'True'
        step_parameter.save()
        step_parameter = StepParameter()
        step_parameter.step = step
        step_parameter.name = 'put-data'
        step_parameter.value = put_data
        step_parameter.save()

    def _create_step(self, rule):
        step = Step()
        step.rule = rule
        step.order = 1
        step.name = 'Output Determination'
        step.step_class = 'quartet_output.steps.OutputParsingStep'
        step.description = 'unit test step'
        step.save()
        step_parameter = StepParameter()
        step_parameter.step = step
        step_parameter.name = 'EPCIS Output Criteria'
        step_parameter.value = 'Test Criteria'
        step_parameter.save()
        return step

    def _create_output_steps(self, rule):
        step = Step()
        step.rule = rule
        step.order = 2
        step.name = 'UnpackHierarchies'
        step.step_class = 'quartet_output.steps.UnpackHierarchyStep'
        step.description = 'unit test unpacking step'
        step.save()

    def _create_comm_step(self, rule):
        step = Step()
        step.rule = rule
        step.order = 3
        step.name = 'CreateCommissioning'
        step.step_class = 'quartet_output.steps.AddCommissioningDataStep'
        step.description = 'unit test commissioning step'
        step.save()

    def _create_epcpyyes_step(self, rule):
        step = Step()
        step.rule = rule
        step.order = 4
        step.name = 'Create EPCIS'
        step.step_class = 'quartet_output.steps.EPCPyYesOutputStep'
        step.description = 'Creates EPCIS XML or JSON and inserts into rule' \
                           'context.'
        step.save()

    def _create_template_step(self, rule):
        step = Step()
        step.rule = rule
        step.order = 5
        step.name = 'Render Template'
        step.step_class = 'quartet_templates.steps.TemplateStep'
        step.description = 'Render the template.'
        step.save()
        StepParameter.objects.create(
            name="Template Name",
            value="RFXCEL SOAP",
            step=step
        )
        StepParameter.objects.create(
            name="Context Key",
            value=ContextKeys.OUTBOUND_EPCIS_MESSAGE_KEY.value,
            step=step
        )
        StepParameter.objects.create(
            name="Auto Escape",
            value="True",
            step=step
        )

    def _create_template(self):
        curpath = os.path.dirname(__file__)
        data_path = os.path.join(curpath,
                                 '../quartet_4nt4r3s/templates/soap/torfxcel_soap.xml')
        data = open(data_path).read()
        Template.objects.create(
            name="RFXCEL SOAP",
            content=data
        )

    def _create_task(self, rule):
        task = Task()
        task.rule = rule
        task.name = 'unit test task'
        task.save()
        return task

    def _add_forward_data_step_parameter(self, step: Step):
        step_parameter = StepParameter()
        step_parameter.step = step
        step_parameter.name = 'Forward Data'
        step_parameter.value = 'True'
        step_parameter.description = 'Whether or not to construct new data ' \
                                     'or to just forward the data in the ' \
                                     'rule.'
        step_parameter.save()

    def _create_task_step(self, rule):
        step = Step()
        step.rule = rule
        step.order = 6
        step.name = 'Create Output Task'
        step.step_class = 'quartet_output.steps.CreateOutputTaskStep'
        step.description = 'Looks for any EPCIS data on the context and ' \
                           'then, if found, creates a new output task using ' \
                           'the configured Output Rule step parameter.'
        step.save()
        step_parameter = StepParameter()
        step_parameter.step = step
        step_parameter.name = 'Output Rule'
        step_parameter.value = 'Transport Rule'
        step_parameter.description = 'The name of the rule to create a new ' \
                                     'task with.'
        step_parameter.save()
        step_parameter = StepParameter()
        step_parameter.step = step
        step_parameter.name = 'run-immediately'
        step_parameter.value = 'True'
        step_parameter.description = 'The name of the rule to create a new ' \
                                     'task with.'
        step_parameter.save()
        return step

    def _parse_test_data(self, test_file='data/epcis.xml',
                         parser_type=BusinessEPCISParser,
                         recursive_decommission=False):
        curpath = os.path.dirname(__file__)
        if isinstance(parser_type, BusinessEPCISParser):
            parser = parser_type(
                os.path.join(curpath, test_file),
                recursive_decommission=recursive_decommission
            )
        else:
            parser = parser_type(
                os.path.join(curpath, test_file),
            )
        message_id = parser.parse()
        print(parser.event_cache)
        parser.clear_cache()
        return message_id, parser

    def tearDown(self):
        pass