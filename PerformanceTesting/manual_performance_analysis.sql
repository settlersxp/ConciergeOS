-- SQLite
SELECT id, run_id, batch_type, request_index, model_name, context_length, vllm_version, thinking_enabled, response_format, json_malformed, response_length, request_sent_time, response_received_time, response_content
FROM test_results;