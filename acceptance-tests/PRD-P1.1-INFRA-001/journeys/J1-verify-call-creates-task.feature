@journey @prd-P1.1-INFRA-001 @J1 @api @db @async @smoke
Scenario J1: Work history verification request creates background task and triggers Prefect flow

  # API layer (TOOL: curl)
  Given I have the Railway dev zenagent URL: https://zenagent-development.up.railway.app
  When I POST to /api/v1/verify with a valid work history payload
  Then the API returns HTTP 200 or 202
  And the response body contains a task_id (store as $task_id)

  # DB layer — immediate (TOOL: direct psql query)
  And the background_tasks table has a row with task_id=$task_id
  And the row has status in ('started', 'pending', 'queued')
  And the row has task_type containing 'work_history' or 'verification'

  # Async layer — Prefect (TOOL: poll curl every 5s, max 120s)
  And eventually a Prefect flow run is created for task_id=$task_id
  And the flow run reaches state "Running" or "Completed" or "Failed"

  # Business outcome
  And the background_tasks row has been updated (status != original status OR result_data is not empty)
