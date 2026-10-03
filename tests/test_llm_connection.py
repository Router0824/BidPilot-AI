import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import HTTPException
from app.agents import LLMGateway, DraftingAgent, build_llm_gateway
from app.core.llm_errors import LLMResponseError, llm_error_message
from app.core.runtime_config import RuntimeLLMConfig, resolve_llm_config, get_runtime_llm_config, save_runtime_llm_config
from app.schemas import LLMConfigUpdate
from app.api.v1.system import test_llm_config


class GatewayTests(unittest.IsolatedAsyncioTestCase):
    async def test_only_deepseek_connection_probe_disables_thinking(self):
        for provider, task, disabled in [('deepseek', 'connection_test', True),
                                         ('deepseek', 'generate_section_content', False),
                                         ('openai', 'connection_test', False),
                                         ('custom', 'connection_test', False)]:
            with self.subTest(provider=provider, task=task):
                calls, mocked = self.transport([('{"ok":true}', 'stop')])
                with mocked:
                    await LLMGateway('test-key', provider=provider).call(task, [], 'json')
                if disabled:
                    self.assertEqual(calls[0]['thinking'], {'type': 'disabled'})
                else:
                    self.assertNotIn('thinking', calls[0])

    async def test_gateway_retains_requested_and_actual_model(self):
        client = httpx.AsyncClient
        transport = httpx.MockTransport(lambda request: httpx.Response(200, json={
            'model': 'deepseek-flash',
            'choices': [{'message': {'content': '{"ok":true}'}, 'finish_reason': 'stop'}],
        }))
        with patch('app.agents.httpx.AsyncClient', side_effect=lambda **kw: client(transport=transport, **kw)):
            result = await LLMGateway('test-key', model='deepseek-v4-flash').call('test', [], 'json')
        self.assertEqual(result['_llm']['model'], 'deepseek-flash')
        self.assertEqual(result['_llm']['selected_model'], 'deepseek-v4-flash')

    async def test_connection_reports_actual_model_when_provider_resolves_alias(self):
        gateway = LLMGateway('test-key', model='deepseek-v4-flash')
        gateway.call = AsyncMock(return_value={'ok': True, '_llm': {'model': 'deepseek-flash'}})
        form = LLMConfigUpdate(provider='deepseek', api_key='test-key')
        with patch('app.api.v1.system.build_llm_gateway', return_value=gateway):
            result = await test_llm_config(form, user={'role': 'admin'})
        self.assertEqual(result.data['requested_model'], 'deepseek-v4-flash')
        self.assertEqual(result.data['model'], 'deepseek-flash')

    def transport(self, responses):
        calls = []
        def handler(request):
            calls.append(json.loads(request.content))
            content, finish = responses[min(len(calls) - 1, len(responses) - 1)]
            return httpx.Response(200, json={"choices": [{"message": {"content": content}, "finish_reason": finish}],
                "usage": {"total_tokens": 20, "prompt_tokens": 10, "completion_tokens": 10}})
        client = httpx.AsyncClient
        return calls, patch('app.agents.httpx.AsyncClient', side_effect=lambda **kw: client(transport=httpx.MockTransport(handler), **kw))

    async def test_retry_counts_every_billable_response(self):
        gateway = LLMGateway('test-key', estimated_cost_per_1k_tokens=1)
        calls, mocked = self.transport([('', 'length'), ('{"ok":true}', 'stop')])
        with mocked:
            result = await gateway.call('test', [], 'json', max_tokens=64)
        self.assertEqual(len(calls), 2)
        self.assertEqual(result['_llm']['usage']['total_tokens'], 40)
        self.assertEqual(gateway.total_tokens, 40)
        self.assertAlmostEqual(gateway.estimated_cost, .04)

    async def test_empty_output_is_not_success_and_retries_are_bounded(self):
        gateway = LLMGateway('test-key')
        calls, mocked = self.transport([('', 'stop')])
        with mocked, self.assertRaises(LLMResponseError):
            await gateway.call('test', [], 'json', max_tokens=64)
        self.assertEqual(len(calls), 3)
        self.assertEqual(gateway.total_tokens, 60)

    async def test_arrays_and_truncated_json_rejected(self):
        for text, finish in [('[]', 'stop'), ('{"ok":true}', 'length')]:
            calls, mocked = self.transport([(text, finish)])
            with mocked, self.assertRaises(LLMResponseError):
                await LLMGateway('test-key').call('test', [], 'json', max_tokens=2048)
            self.assertEqual(len(calls), 1)

    async def test_budget_stops_retry(self):
        gateway = LLMGateway('test-key', cost_limit_per_project=.01, estimated_cost_per_1k_tokens=1)
        calls, mocked = self.transport([('', 'length')])
        with mocked, self.assertRaises(LLMResponseError):
            await gateway.call('test', [], 'json', max_tokens=64)
        self.assertEqual(len(calls), 1)

    async def test_real_drafting_failure_does_not_become_mock_content(self):
        gateway = LLMGateway('test-key')
        gateway.call = AsyncMock(side_effect=LLMResponseError('request failed'))
        agent = DraftingAgent(gateway)
        with patch.object(agent, '_rule_generate_section_content') as fallback:
            with self.assertRaises(LLMResponseError):
                await agent._generate_section_content('技术方案', {}, [])
            fallback.assert_not_called()

    async def test_connection_tests_unsaved_form_without_persisting_or_reloading(self):
        gateway = LLMGateway('test-key')
        gateway.call = AsyncMock(return_value={'ok': True, 'message': 'connected'})
        form = LLMConfigUpdate(provider='custom', api_key='new-test-key', base_url='https://example.test/v1', model='test-model')
        with patch('app.api.v1.system.build_llm_gateway', return_value=gateway) as build, \
             patch('app.api.v1.system.reload_llm_gateway') as reload, \
             patch('app.api.v1.system.save_runtime_llm_config') as save:
            await test_llm_config(form, user={'role': 'admin'})
            self.assertEqual(build.call_args.args[0].api_key, 'new-test-key')
            save.assert_not_called()
            reload.assert_not_called()

    async def test_connection_requires_true_not_truthy(self):
        gateway = LLMGateway('test-key')
        form = LLMConfigUpdate(provider='custom', api_key='test-key', base_url='https://example.test/v1', model='test-model')
        for response in ({'ok': False}, {'ok': 'true'}, {'message': 'hello'}):
            gateway.call = AsyncMock(return_value=response)
            with patch('app.api.v1.system.build_llm_gateway', return_value=gateway), self.assertRaises(HTTPException):
                await test_llm_config(form, user={'role': 'admin'})


class ConfigurationTests(unittest.TestCase):
    def test_deepseek_defaults_and_explicit_models_are_preserved(self):
        gateway = build_llm_gateway(RuntimeLLMConfig(provider='deepseek', api_key='test-key'))
        self.assertEqual(gateway.provider, 'deepseek')
        self.assertEqual(gateway.model, 'deepseek-flash')
        self.assertEqual(gateway.model_routing['extract_requirements'], 'deepseek-flash')
        self.assertEqual(gateway.model_routing['generate_section_content'], 'deepseek-v4-pro')
        legacy = build_llm_gateway(RuntimeLLMConfig(provider='deepseek', api_key='test-key', model='deepseek-v4-flash'))
        self.assertEqual(legacy.model, 'deepseek-v4-flash')

    def test_custom_model_is_used_for_all_routes_unless_overridden(self):
        runtime = RuntimeLLMConfig(provider='custom', base_url='https://example.test/v1', api_key='test-key', model='my-model')
        gateway = build_llm_gateway(runtime)
        self.assertEqual(gateway.model_routing['generate_section_content'], 'my-model')
        self.assertEqual(gateway.model_routing['extract_requirements'], 'my-model')

    def test_old_key_cannot_be_sent_to_different_service(self):
        current = RuntimeLLMConfig(provider='custom', base_url='https://old.example/v1', api_key='old-test-key')
        with patch('app.core.runtime_config.get_runtime_llm_config', return_value=current):
            with self.assertRaises(ValueError):
                resolve_llm_config({'provider': 'custom', 'base_url': 'https://new.example/v1', 'model': 'model'})
            result = resolve_llm_config({'provider': 'custom', 'base_url': 'https://old.example/v1', 'model': 'model'})
            self.assertEqual(result.api_key, 'old-test-key')

    def test_explicit_zero_and_cleared_key_override_environment(self):
        from app.core.config import settings
        with tempfile.TemporaryDirectory() as directory, patch('app.core.runtime_config.CONFIG_PATH', str(Path(directory) / 'config.json')), \
             patch.object(settings, 'LLM_COST_LIMIT_PER_PROJECT', 42), patch.object(settings, 'LLM_API_KEY', 'env-test-key'):
            save_runtime_llm_config({'provider': 'mock', 'cost_limit_per_project': 0})
            result = get_runtime_llm_config()
            self.assertEqual(result.cost_limit_per_project, 0)
            self.assertFalse(result.api_key)
            self.assertEqual(os.stat(Path(directory) / 'config.json').st_mode & 0o777, 0o600)

    def test_full_chat_url_is_normalized_and_credentials_rejected(self):
        form = LLMConfigUpdate(base_url='https://example.test/v1/chat/completions/')
        self.assertEqual(form.base_url, 'https://example.test/v1')
        for url in ['https://user:secret@example.test/v1', 'https://example.test/v1?api_key=test']:
            with self.assertRaises(ValueError):
                LLMConfigUpdate(base_url=url)

    def test_error_does_not_echo_provider_body_or_credential_url(self):
        response = httpx.Response(401, text='test-key', request=httpx.Request('POST', 'https://example.test/?api_key=test-key'))
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            message = llm_error_message(error)
            self.assertNotIn('test-key', message)
            self.assertIn('401', message)
