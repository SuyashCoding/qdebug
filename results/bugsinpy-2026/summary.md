# qdebug on BugsInPy

229 bugs attempted, 196 reproduced on this machine. GroundTruthOracle, noise 0, tuned policy, assumed ε = 0.1. Spectrum: the bug's test file(s) only.

## Setup outcome

| status | bugs |
|---|---|
| error | 2 |
| no trace | 6 |
| nondeterministic | 2 |
| not reproducible | 30 |
| ok | 186 |
| setup failed | 3 |

## Per strategy (bugs with a completed session)

| strategy | sessions | function found | found before zoom | func. Q (mean / median) | line Q (mean) | true line in region | region size |
|---|---|---|---|---|---|---|---|
| infogain | 186 | 60% | 61% | 5.8 / 3 | 3.5 | 39% | 1.0 |
| topdown | 186 | 56% | 49% | 9.1 / 6 | 3.0 | 35% | 1.0 |
| divide | 186 | 60% | 57% | 8.6 / 5.5 | 3.1 | 38% | 1.0 |

## infogain against SBFL (Ochiai on the same spectrum)

The same 186 sessions. SBFL "top-k" means the buggy function or line is among the k most suspicious; qdebug reports one function and a region of 1.0 lines on average.

| | qdebug | SBFL top-1 | SBFL top-3 | SBFL top-5 |
|---|---|---|---|---|
| buggy function | 112 / 186 | 71 / 186 | 103 / 186 | 118 / 186 |
| buggy line | 72 / 186 | 33 / 186 | 61 / 186 | 78 / 186 |

By tree size: 83 of 128 failing tests with fewer than 100 calls, 29 of 58 with 100 or more (median tree: 19 calls).

## Per project

| project | attempted | reproduced | infogain: found / line | topdown: found / line | divide: found / line |
|---|---|---|---|---|---|
| PySnooper | 3 | 2 | 0 / 0 of 1 | 0 / 0 of 1 | 0 / 0 of 1 |
| black | 23 | 22 | 10 / 7 of 22 | 7 / 4 of 22 | 10 / 6 of 22 |
| cookiecutter | 4 | 3 | 2 / 1 of 3 | 2 / 1 of 3 | 2 / 1 of 3 |
| fastapi | 16 | 16 | 4 / 2 of 15 | 4 / 2 of 15 | 4 / 2 of 15 |
| httpie | 5 | 5 | 2 / 0 of 5 | 1 / 0 of 5 | 1 / 0 of 5 |
| luigi | 33 | 27 | 12 / 10 of 26 | 12 / 10 of 26 | 12 / 10 of 26 |
| sanic | 5 | 3 | 2 / 1 of 2 | 2 / 1 of 2 | 2 / 1 of 2 |
| scrapy | 40 | 27 | 18 / 15 of 26 | 17 / 14 of 26 | 18 / 15 of 26 |
| thefuck | 32 | 24 | 19 / 12 of 24 | 19 / 12 of 24 | 19 / 12 of 24 |
| tornado | 16 | 15 | 3 / 2 of 14 | 3 / 2 of 14 | 3 / 2 of 14 |
| tqdm | 9 | 9 | 6 / 6 of 9 | 6 / 5 of 9 | 6 / 5 of 9 |
| youtube-dl | 43 | 43 | 34 / 16 of 39 | 31 / 14 of 39 | 34 / 16 of 39 |

## Per bug

| bug | status | patch | buggy function(s) | SBFL func / line rank | infogain: Q / found / line | topdown: Q / found / line | divide: Q / found / line |
|---|---|---|---|---|---|---|---|
| PySnooper 1 | not reproducible: buggy: passed (all requirements) | | | | | | |
| PySnooper 2 | ok |  | `(module level)` | - / - | - | - | - |
| PySnooper 3 | ok | change | `pysnooper/pysnooper.py::get_write_function` | 1 / - | 3+4 / ✗ / ✗ | 4+4 / ✗ / ✗ | 5+4 / ✗ / ✗ |
| black 1 | ok | change | `black.py::reformat_many` | 1 / 10 | 2+3 / ✓ / ✓ | 13+3 / ✓ / ✓ | 6+3 / ✓ / ✓ |
| black 2 | ok | change | `(module level)` | - / 1346 | 1+0 / ✗ / ✗ | 1+0 / ✗ / ✗ | 1+0 / ✗ / ✗ |
| black 3 | ok | change | `black.py::main` | 95 / - | 6+0 / ✗ / ✗ | 5+0 / ✗ / ✗ | 5+0 / ✗ / ✗ |
| black 4 | ok | change | `black.py::EmptyLineTracker.maybe_empty_lines` | 25 / 253 | 11+3 / ✓ / ✓ | 33+0 / ✗ / ✗ | 22+3 / ✓ / ✓ |
| black 5 | ok | change | `black.py::Line.maybe_remove_trailing_comma black.py::bracket_split_build_line` | 33 / 464 | 1+0 / ✗ / ✗ | 1+0 / ✗ / ✗ | 1+0 / ✗ / ✗ |
| black 6 | ok | change | `black.py::get_grammars black.py::lib2to3_parse blib2to3/pgen2/driver.py::Driver.__init__ blib2to3/pgen2/driver.py::Driver.parse_stream_raw blib2to3/pgen2/driver.py::Driver.parse_string` | 91 / 66 | 1+0 / ✗ / ✗ | 1+0 / ✗ / ✗ | 1+0 / ✗ / ✗ |
| black 7 | ok | change | `black.py::normalize_invisible_parens` | 17 / 196 | 11+5 / ✓ / ✓ | 25+5 / ✓ / ✓ | 32+0 / ✗ / ✗ |
| black 8 | ok | change | `black.py::bracket_split_build_line` | 4 / 36 | 4+10 / ✓ / ✓ | 33+0 / ✗ / ✗ | 33+0 / ✗ / ✗ |
| black 9 | ok | change | `black.py::get_grammars` | 5 / 1 | 7+2 / ✓ / ✓ | 5+2 / ✓ / ✓ | 22+2 / ✓ / ✓ |
| black 10 | ok | change | `blib2to3/pgen2/driver.py::Driver._partially_consume_prefix` | 11 / 1 | 31+0 / ✗ / ✗ | 31+0 / ✗ / ✗ | 28+7 / ✓ / ✓ |
| black 11 | ok | change | `black.py::normalize_prefix black.py::should_explode` | 13 / 353 | 32+0 / ✗ / ✗ | 32+0 / ✗ / ✗ | 30+0 / ✗ / ✗ |
| black 12 | ok | change | `black.py::BracketTracker.maybe_decrement_after_for_loop_variable black.py::BracketTracker.maybe_decrement_after_lambda_arguments black.py::BracketTracker.maybe_increment_for_loop_variable black.py::BracketTracker.maybe_increment_lambda_arguments` | 20 / 9 | 7+6 / ✗ / ✗ | 32+0 / ✗ / ✗ | 30+0 / ✗ / ✗ |
| black 13 | ok | change | `(module level)` | - / 64 | 18+10 / ✗ / ✗ | 21+10 / ✗ / ✗ | 17+10 / ✗ / ✗ |
| black 14 | ok | change | `black.py::get_future_imports` | 1 / 1 | 13+5 / ✓ / ✓ | 19+5 / ✓ / ✓ | 20+5 / ✓ / ✓ |
| black 15 | ok | change | `black.py::DebugVisitor.show black.py::EmptyLineTracker.maybe_empty_lines black.py::FormatError.__init__ black.py::FormatError.leaf_from_consumed black.py::FormatError.trim_prefix black.py::UnformattedLines.__str__ black.py::UnformattedLines.append black.py::UnformattedLines.append_comment black.py::UnformattedLines.maybe_increment_for_loop_variable black.py::UnformattedLines.maybe_remove_trailing_comma black.py::container_of black.py::hide_fmt_off black.py::normalize_fmt_off` | 1 / 1 | 4+3 / ✓ / ✗ | 7+3 / ✓ / ✗ | 30+0 / ✓ / ✗ |
| black 16 | ok | change | `(module level)` | - / 3 | 0+0 / ✗ / ✗ | 0+0 / ✗ / ✗ | 0+0 / ✗ / ✗ |
| black 17 | ok | change | `black.py::decode_bytes black.py::lib2to3_parse` | 2 / 3 | 1+2 / ✓ / ✗ | 2+2 / ✓ / ✗ | 2+2 / ✓ / ✗ |
| black 18 | ok | change | `black.py::format_file_in_place black.py::format_stdin_to_stdout black.py::lib2to3_parse` | 1 / 1 | 27+0 / ✓ / ✗ | 1+0 / ✓ / ✗ | 1+0 / ✓ / ✗ |
| black 19 | ok | insert | `black.py::EmptyLineTracker._maybe_empty_lines` | 11 / 29 | 16+5 / ✓ / ✓ | 31+0 / ✗ / ✗ | 11+5 / ✓ / ✓ |
| black 20 | ok | change | `black.py::format_file_in_place` | 3 / 10 | 23+0 / ✗ / ✗ | 5+0 / ✗ / ✗ | 19+0 / ✗ / ✗ |
| black 21 | not reproducible: buggy: passed (all requirements) | | | | | | |
| black 22 | ok | change | `black.py::Line.__str__ black.py::Line.append black.py::Line.append_comment black.py::Line.is_comment black.py::Line.last_non_delimiter black.py::Line.maybe_adapt_standalone_comment black.py::Line.maybe_remove_trailing_comma black.py::UnformattedLines.maybe_adapt_standalone_comment` | 3 / 16 | 14+10 / ✗ / ✗ | 33+0 / ✗ / ✗ | 33+0 / ✗ / ✗ |
| black 23 | ok | change+insert | `black.py::assert_equivalent black.py::lib2to3_parse black.py::whitespace` | 3 / 145 | 14+13 / ✗ / ✗ | 31+0 / ✗ / ✗ | 14+7 / ✓ / ✗ |
| cookiecutter 1 | ok | change | `cookiecutter/generate.py::generate_context` | 1 / 4 | 1+3 / ✓ / ✓ | 2+3 / ✓ / ✓ | 1+3 / ✓ / ✓ |
| cookiecutter 2 | ok | change | `cookiecutter/hooks.py::find_hook cookiecutter/hooks.py::run_hook` | 1 / 1 | 3+4 / ✓ / ✗ | 5+4 / ✓ / ✗ | 3+4 / ✓ / ✗ |
| cookiecutter 3 | not reproducible: fixed: failed (all requirements) | | | | | | |
| cookiecutter 4 | ok | change+insert | `cookiecutter/generate.py::generate_files cookiecutter/hooks.py::run_hook cookiecutter/hooks.py::run_script cookiecutter/hooks.py::run_script_with_context` | 11 / 27 | 1+0 / ✗ / ✗ | 1+0 / ✗ / ✗ | 1+0 / ✗ / ✗ |
| fastapi 1 | ok | change+insert | `fastapi/applications.py::FastAPI.add_api_route fastapi/applications.py::FastAPI.api_route fastapi/applications.py::FastAPI.api_route.<locals>.decorator fastapi/applications.py::FastAPI.delete fastapi/applications.py::FastAPI.get fastapi/applications.py::FastAPI.head fastapi/applications.py::FastAPI.options fastapi/applications.py::FastAPI.patch fastapi/applications.py::FastAPI.post fastapi/applications.py::FastAPI.put fastapi/applications.py::FastAPI.trace fastapi/encoders.py::jsonable_encoder fastapi/openapi/utils.py::get_openapi fastapi/openapi/utils.py::get_openapi_security_definitions fastapi/routing.py::APIRoute.__init__ fastapi/routing.py::APIRoute.get_route_handler fastapi/routing.py::APIRouter.add_api_route fastapi/routing.py::APIRouter.api_route fastapi/routing.py::APIRouter.api_route.<locals>.decorator fastapi/routing.py::APIRouter.delete fastapi/routing.py::APIRouter.get fastapi/routing.py::APIRouter.head fastapi/routing.py::APIRouter.include_router fastapi/routing.py::APIRouter.options fastapi/routing.py::APIRouter.patch fastapi/routing.py::APIRouter.post fastapi/routing.py::APIRouter.put fastapi/routing.py::APIRouter.trace fastapi/routing.py::_prepare_response_content fastapi/routing.py::get_request_handler` | 1 / 8 | 12+0 / ✓ / ✗ | 5+0 / ✓ / ✗ | 6+0 / ✓ / ✗ |
| fastapi 2 | ok | change | `fastapi/routing.py::APIRouter.add_api_websocket_route` | 199 / - | 0+0 / ✗ / ✗ | 0+0 / ✗ / ✗ | 0+0 / ✗ / ✗ |
| fastapi 3 | ok | change | `(module level)` | - / 41 | 3+0 / ✗ / ✗ | 3+0 / ✗ / ✗ | 3+0 / ✗ / ✗ |
| fastapi 4 | ok | change | `fastapi/openapi/utils.py::get_openapi_path` | 10 / 159 | 7+8 / ✓ / ✓ | 10+8 / ✓ / ✓ | 6+8 / ✓ / ✓ |
| fastapi 5 | ok | change | `fastapi/utils.py::create_cloned_field` | 225 / - | 12+0 / ✗ / ✗ | 5+0 / ✗ / ✗ | 6+0 / ✗ / ✗ |
| fastapi 6 | ok | change | `(module level)` | - / 56 | 8+0 / ✗ / ✗ | 6+0 / ✗ / ✗ | 7+0 / ✗ / ✗ |
| fastapi 7 | ok | change | `(module level)` | - / 3 | 5+0 / ✗ / ✗ | 5+0 / ✗ / ✗ | 5+0 / ✗ / ✗ |
| fastapi 8 | ok | change | `fastapi/routing.py::APIRouter.add_api_route fastapi/routing.py::APIRouter.include_router` | 156 / - | 0+0 / ✗ / ✗ | 0+0 / ✗ / ✗ | 0+0 / ✗ / ✗ |
| fastapi 9 | ok | change | `fastapi/dependencies/utils.py::get_body_field` | - / - | nondeterministic | nondeterministic | nondeterministic |
| fastapi 10 | ok | insert | `fastapi/routing.py::serialize_response` | 3 / 78 | 3+5 / ✓ / ✗ | 5+5 / ✓ / ✗ | 3+5 / ✓ / ✗ |
| fastapi 11 | ok | change | `fastapi/dependencies/utils.py::is_scalar_field` | 125 / - | 6+0 / ✗ / ✗ | 1+0 / ✗ / ✗ | 3+0 / ✗ / ✗ |
| fastapi 12 | ok | change | `(module level)` | - / 6 | 6+0 / ✗ / ✗ | 6+0 / ✗ / ✗ | 6+0 / ✗ / ✗ |
| fastapi 13 | ok | change | `fastapi/routing.py::APIRouter.include_router` | 107 / - | 0+0 / ✗ / ✗ | 0+0 / ✗ / ✗ | 0+0 / ✗ / ✗ |
| fastapi 14 | ok | change | `(module level)` | - / - | 0+0 / ✗ / ✗ | 0+0 / ✗ / ✗ | 0+0 / ✗ / ✗ |
| fastapi 15 | ok | insert | `fastapi/routing.py::APIRouter.include_router` | 103 / - | 0+0 / ✗ / ✗ | 0+0 / ✗ / ✗ | 0+0 / ✗ / ✗ |
| fastapi 16 | ok | change | `fastapi/encoders.py::jsonable_encoder` | 1 / 1 | 1+2 / ✓ / ✓ | 1+2 / ✓ / ✓ | 1+2 / ✓ / ✓ |
| httpie 1 | ok | change | `httpie/downloads.py::get_unique_filename` | 80 / - | 0+0 / ✗ / ✗ | 0+0 / ✗ / ✗ | 0+0 / ✗ / ✗ |
| httpie 2 | ok | change+insert | `httpie/client.py::get_response httpie/core.py::main` | 1 / 5 | 10+0 / ✓ / ✗ | 2+0 / ✓ / ✗ | 5+0 / ✓ / ✗ |
| httpie 3 | ok | insert | `httpie/sessions.py::Session.update_headers` | 10 / 250 | 21+0 / ✗ / ✗ | 4+0 / ✗ / ✗ | 6+0 / ✗ / ✗ |
| httpie 4 | ok | change | `httpie/models.py::HTTPRequest.headers` | 34 / 452 | 28+5 / ✓ / ✗ | 4+0 / ✗ / ✗ | 10+0 / ✗ / ✗ |
| httpie 5 | ok | change | `httpie/cli.py::KeyValueType.__call__` | 2 / 14 | 1+1 / ✗ / ✗ | 2+1 / ✗ / ✗ | 1+1 / ✗ / ✗ |
| luigi 1 | ok | change | `luigi/server.py::MetricsHandler.get` | - / - | error | error | error |
| luigi 2 | not reproducible: fixed: failed (v3: all requirements except: dropped pager==3.3 pywin32==227 SOAP | | | | | | |
| luigi 3 | ok | change | `luigi/parameter.py::TupleParameter.parse` | 1 / 1 | 2+2 / ✓ / ✓ | 5+2 / ✓ / ✓ | 6+2 / ✓ / ✓ |
| luigi 4 | ok | change | `luigi/contrib/redshift.py::S3CopyToTable.copy` | 2 / 7 | 7+4 / ✗ / ✗ | 5+4 / ✗ / ✗ | 6+4 / ✗ / ✗ |
| luigi 5 | ok | change | `luigi/util.py::inherits.__call__ luigi/util.py::inherits.__call__.<locals>.Wrapped.clone_parent luigi/util.py::requires.__call__ luigi/util.py::requires.__call__.<locals>.Wrapped.requires` | 11 / 42 | 30+0 / ✗ / ✗ | 3+0 / ✗ / ✗ | 10+0 / ✗ / ✗ |
| luigi 6 | ok | change | `luigi/parameter.py::DictParameter._DictParamEncoder.default luigi/parameter.py::DictParameter.serialize luigi/parameter.py::ListParameter.normalize luigi/parameter.py::ListParameter.parse luigi/parameter.py::ListParameter.serialize luigi/parameter.py::TupleParameter.parse luigi/parameter.py::TupleParameter.serialize luigi/parameter.py::_recursively_freeze` | 5 / 12 | 5+1 / ✓ / ✓ | 18+1 / ✓ / ✓ | 8+1 / ✓ / ✓ |
| luigi 7 | ok | change | `luigi/scheduler.py::Scheduler.add_task` | 42 / 236 | 12+6 / ✗ / ✗ | 5+4 / ✗ / ✗ | 8+6 / ✗ / ✗ |
| luigi 8 | ok | change | `luigi/contrib/redshift.py::S3CopyToTable.does_table_exist` | 1 / - | 5+4 / ✗ / ✗ | 3+0 / ✓ / ✗ | 5+4 / ✗ / ✗ |
| luigi 9 | ok | change | `luigi/execution_summary.py::_depth_first_search luigi/execution_summary.py::_partition_tasks luigi/execution_summary.py::_summary_format` | 62 / 378 | 31+3 / ✗ / ✗ | 5+5 / ✗ / ✗ | 31+3 / ✗ / ✗ |
| luigi 10 | ok | change | `luigi/scheduler.py::Worker.get_pending_tasks` | 3 / 2 | 11+15 / ✗ / ✗ | 5+4 / ✗ / ✗ | 6+4 / ✗ / ✗ |
| luigi 11 | ok | change | `luigi/scheduler.py::Scheduler.get_work` | 14 / 18 | 11+6 / ✗ / ✗ | 6+4 / ✗ / ✗ | 11+4 / ✗ / ✗ |
| luigi 12 | ok | change | `luigi/contrib/hdfs/clients.py::get_autoconfig_client` | 7 / 17 | 30+0 / ✗ / ✗ | 5+0 / ✗ / ✗ | 13+0 / ✗ / ✗ |
| luigi 13 | ok | change | `luigi/file.py::LocalFileSystem.move` | 1 / 1 | 1+3 / ✓ / ✓ | 8+3 / ✓ / ✓ | 7+3 / ✓ / ✓ |
| luigi 14 | ok | change | `luigi/scheduler.py::SimpleTaskState.set_status luigi/scheduler.py::Task.can_disable luigi/scheduler.py::Task.has_excessive_failures` | 10 / 1 | 12+10 / ✗ / ✗ | 5+10 / ✗ / ✗ | 6+10 / ✗ / ✗ |
| luigi 15 | ok | change | `luigi/scheduler.py::SimpleTaskState.get_necessary_tasks` | 7 / 2 | 9+6 / ✓ / ✓ | 26+6 / ✓ / ✓ | 7+6 / ✓ / ✓ |
| luigi 16 | ok | change | `luigi/scheduler.py::CentralPlannerScheduler.prune` | 14 / 78 | 10+6 / ✓ / ✓ | 15+6 / ✓ / ✓ | 14+6 / ✓ / ✓ |
| luigi 17 | not reproducible: fixed: failed (v3: all requirements except: dropped pager==3.3 pywin32==227 SOAP | | | | | | |
| luigi 18 | ok | change | `luigi/scheduler.py::SimpleTaskState.set_status` | 24 / 25 | 16+4 / ✓ / ✓ | 12+4 / ✓ / ✓ | 14+4 / ✓ / ✓ |
| luigi 19 | ok | change | `luigi/scheduler.py::SimpleTaskState.set_status` | 30 / 235 | 9+7 / ✓ / ✓ | 24+7 / ✓ / ✓ | 10+7 / ✓ / ✓ |
| luigi 20 | not reproducible: fixed: failed (v3: all requirements except: dropped pager==3.3 pypiwin32==223 py | | | | | | |
| luigi 21 | not reproducible: fixed: failed (v3: all requirements except: dropped pager==3.3 pypiwin32==223 py | | | | | | |
| luigi 22 | ok | change | `luigi/scheduler.py::Worker.__init__` | 2 / - | 4+0 / ✗ / ✗ | 4+0 / ✗ / ✗ | 4+0 / ✗ / ✗ |
| luigi 23 | ok | change | `luigi/interface.py::WorkerSchedulerFactory.create_local_scheduler luigi/scheduler.py::CentralPlannerScheduler.get_work luigi/scheduler.py::Worker.__init__` | 732 / - | 4+10 / ✗ / ✗ | 5+10 / ✗ / ✗ | 4+10 / ✗ / ✗ |
| luigi 24 | not reproducible: fixed: failed (v3: all requirements except: dropped pager==3.3 pypiwin32==223 py | | | | | | |
| luigi 25 | not reproducible: fixed: failed (v3: all requirements except: dropped pager==3.3 pypiwin32==223 py | | | | | | |
| luigi 26 | ok | change | `luigi/contrib/hadoop_jar.py::HadoopJarJobRunner.run_job` | 3 / 4 | 5+8 / ✓ / ✗ | 7+8 / ✓ / ✗ | 5+8 / ✓ / ✗ |
| luigi 27 | ok | change | `luigi/parameter.py::Parameter.add_to_cmdline_parser luigi/parameter.py::Parameter.parse_from_args luigi/parameter.py::Parameter.parse_from_input luigi/parameter.py::Parameter.set_global_from_args` | 9 / 28 | 13+3 / ✓ / ✗ | 2+0 / ✗ / ✗ | 9+3 / ✓ / ✗ |
| luigi 28 | ok | change | `luigi/contrib/hive.py::HiveCommandClient.table_exists` | 1 / 3 | 1+2 / ✓ / ✓ | 4+2 / ✓ / ✓ | 3+2 / ✓ / ✓ |
| luigi 29 | ok | change | `luigi/task_register.py::Register.__get_reg` | 1 / 3 | 2+7 / ✓ / ✓ | 15+7 / ✓ / ✓ | 14+7 / ✓ / ✓ |
| luigi 30 | ok | change | `luigi/worker.py::TaskProcess.run` | 9 / 361 | 6+5 / ✗ / ✗ | 8+0 / ✗ / ✗ | 14+5 / ✗ / ✗ |
| luigi 31 | ok | change | `luigi/scheduler.py::CentralPlannerScheduler.get_work` | 6 / 28 | 8+4 / ✗ / ✗ | 5+4 / ✗ / ✗ | 7+4 / ✗ / ✗ |
| luigi 32 | ok | insert | `(module level)` | - / - | 3+5 / ✗ / ✗ | 5+5 / ✗ / ✗ | 3+5 / ✗ / ✗ |
| luigi 33 | ok | change | `luigi/task.py::Task.get_param_values` | 5 / 36 | 3+4 / ✓ / ✓ | 7+4 / ✓ / ✓ | 4+4 / ✓ / ✓ |
| sanic 1 | ok | change | `sanic/app.py::Sanic.register_named_middleware` | 1 / 4 | 10+4 / ✓ / ✓ | 25+4 / ✓ / ✓ | 22+4 / ✓ / ✓ |
| sanic 2 | not reproducible: buggy: passed (v3: all requirements except: dropped pager==3.3 pywin32==227 SOAP | | | | | | |
| sanic 3 | ok | change | `sanic/app.py::Sanic.url_for` | 4 / 53 | 4+6 / ✓ / ✗ | 10+6 / ✓ / ✗ | 7+6 / ✓ / ✗ |
| sanic 4 | setup failed: RunnerError: pytest reported a usage error (exit 4) in /work/w/checkouts/sanic-4 | | | | | | |
| sanic 5 | ok | change | `(module level)` | - / - | error | error | error |
| scrapy 1 | not reproducible: fixed: failed (v3: all requirements except: dropped pywin32==227 SOAPpy==0.12.22 | | | | | | |
| scrapy 2 | ok | change | `scrapy/utils/datatypes.py::LocalCache.__setitem__` | 2 / 3 | 1+1 / ✓ / ✓ | 3+1 / ✓ / ✓ | 2+1 / ✓ / ✓ |
| scrapy 3 | ok | change | `scrapy/downloadermiddlewares/redirect.py::RedirectMiddleware.process_response` | 4 / 4 | 8+0 / ✗ / ✗ | 31+0 / ✗ / ✗ | 15+5 / ✗ / ✗ |
| scrapy 4 | ok | change | `scrapy/contracts/__init__.py::ContractsManager._clean_req.<locals>.eb_wrapper` | 1 / 2 | 3+3 / ✓ / ✓ | 8+3 / ✓ / ✓ | 4+3 / ✓ / ✓ |
| scrapy 5 | ok | insert | `scrapy/http/response/__init__.py::Response.follow` | 3 / 5 | 4+5 / ✓ / ✓ | 7+5 / ✓ / ✓ | 4+5 / ✓ / ✓ |
| scrapy 6 | not reproducible: fixed: failed (v3: all requirements except: dropped pywin32==227 SOAPpy==0.12.22 | | | | | | |
| scrapy 7 | not reproducible: buggy: passed (v3: all requirements except: dropped pywin32==227 SOAPpy==0.12.22 | | | | | | |
| scrapy 8 | ok | insert | `scrapy/item.py::ItemMeta.__new__` | 1 / 1 | 1+9 / ✓ / ✓ | 3+9 / ✓ / ✓ | 1+9 / ✓ / ✓ |
| scrapy 9 | not reproducible: fixed: failed (v3: all requirements except: dropped pywin32==227 SOAPpy==0.12.22 | | | | | | |
| scrapy 10 | ok | change | `scrapy/downloadermiddlewares/redirect.py::RedirectMiddleware.process_response` | 4 / 3 | 8+5 / ✓ / ✗ | 15+5 / ✓ / ✗ | 12+5 / ✓ / ✗ |
| scrapy 11 | not reproducible: fixed: failed (v3: all requirements except: dropped pywin32==227 SOAPpy==0.12.22 | | | | | | |
| scrapy 12 | not reproducible: fixed: failed (v3: all requirements except: dropped pywin32==227 SOAPpy==0.12.22 | | | | | | |
| scrapy 13 | not reproducible: buggy: passed (v3: all requirements except: dropped pywin32==227 SOAPpy==0.12.22 | | | | | | |
| scrapy 14 | not reproducible: fixed: failed (v3: all requirements except: dropped pywin32==227 SOAPpy==0.12.22 | | | | | | |
| scrapy 15 | ok | change | `scrapy/utils/url.py::_safe_ParseResult` | 3 / 5 | 2+2 / ✓ / ✓ | 5+2 / ✓ / ✓ | 2+2 / ✓ / ✓ |
| scrapy 16 | ok | change | `scrapy/utils/url.py::_unquotepath scrapy/utils/url.py::canonicalize_url scrapy/utils/url.py::parse_url` | 1 / 1 | 3+5 / ✓ / ✓ | 5+5 / ✓ / ✓ | 4+5 / ✓ / ✓ |
| scrapy 17 | ok | change | `scrapy/utils/response.py::response_status_message` | 1 / 3 | 2+1 / ✓ / ✓ | 5+1 / ✓ / ✓ | 4+1 / ✓ / ✓ |
| scrapy 18 | ok | change | `scrapy/responsetypes.py::ResponseTypes.from_content_disposition` | 1 / 3 | 5+3 / ✓ / ✓ | 6+3 / ✓ / ✓ | 5+3 / ✓ / ✓ |
| scrapy 19 | ok | change | `scrapy/http/cookies.py::WrappedRequest.get_origin_req_host` | 20 / 55 | 15+0 / ✗ / ✗ | 4+0 / ✗ / ✗ | 7+0 / ✗ / ✗ |
| scrapy 20 | ok | change | `(module level)` | - / 2 | 17+0 / ✗ / ✗ | 9+0 / ✗ / ✗ | 10+0 / ✗ / ✗ |
| scrapy 21 | ok | change | `scrapy/downloadermiddlewares/robotstxt.py::RobotsTxtMiddleware._robots_error` | 3 / 9 | 31+0 / ✗ / ✗ | 4+0 / ✗ / ✗ | 11+0 / ✗ / ✗ |
| scrapy 22 | ok | change | `scrapy/exporters.py::XmlItemExporter._export_xml_field` | 1 / - | 3+4 / ✓ / ✗ | 11+4 / ✓ / ✗ | 4+4 / ✓ / ✗ |
| scrapy 23 | ok | change | `scrapy/downloadermiddlewares/httpproxy.py::HttpProxyMiddleware._get_proxy scrapy/downloadermiddlewares/httpproxy.py::HttpProxyMiddleware._set_proxy` | 1 / 1 | 1+4 / ✓ / ✓ | 4+4 / ✓ / ✓ | 2+4 / ✓ / ✓ |
| scrapy 24 | ok | change | `scrapy/core/downloader/handlers/http11.py::TunnelingTCP4ClientEndpoint.requestTunnel` | 5 / 8 | 0+0 / ✗ / ✗ | 0+0 / ✗ / ✗ | 0+0 / ✗ / ✗ |
| scrapy 25 | not reproducible: fixed: failed (v3: all requirements except: dropped pywin32==227 SOAPpy==0.12.22 | | | | | | |
| scrapy 26 | setup failed: RunnerError: pytest reported a usage error (exit 4) in /work/w/checkouts/scrapy- | | | | | | |
| scrapy 27 | ok | change | `scrapy/downloadermiddlewares/redirect.py::RedirectMiddleware.process_response` | 83 / 265 | 19+4 / ✓ / ✗ | 12+4 / ✓ / ✗ | 14+4 / ✓ / ✗ |
| scrapy 28 | not reproducible: fixed: failed (v3: all requirements except: dropped pywin32==227 SOAPpy==0.12.22 | | | | | | |
| scrapy 29 | ok | change | `scrapy/utils/request.py::request_httprepr` | 2 / 9 | 5+3 / ✓ / ✓ | 8+3 / ✓ / ✓ | 6+3 / ✓ / ✓ |
| scrapy 30 | ok | change | `scrapy/utils/testproc.py::TestProcessProtocol.__init__` | 3 / 15 | 1+3 / ✓ / ✓ | 1+3 / ✓ / ✓ | 1+3 / ✓ / ✓ |
| scrapy 31 | ok | change | `scrapy/http/cookies.py::WrappedRequest.get_header scrapy/http/cookies.py::WrappedRequest.header_items scrapy/http/cookies.py::WrappedResponse.get_all` | 13 / 59 | 4+3 / ✗ / ✗ | 11+3 / ✗ / ✗ | 5+2 / ✓ / ✓ |
| scrapy 32 | ok | change | `scrapy/crawler.py::CrawlerProcess.__init__` | 1 / 3 | 8+3 / ✓ / ✓ | 6+3 / ✓ / ✓ | 8+3 / ✓ / ✓ |
| scrapy 33 | ok |  | `(module level)` | - / - | - | - | - |
| scrapy 34 | ok | change | `scrapy/item.py::ItemMeta.__new__` | 4 / 8 | 1+3 / ✗ / ✗ | 7+3 / ✗ / ✗ | 3+3 / ✗ / ✗ |
| scrapy 35 | ok | change | `scrapy/crawler.py::_get_spider_loader` | 2 / 12 | 5+5 / ✓ / ✓ | 11+5 / ✓ / ✓ | 7+5 / ✓ / ✓ |
| scrapy 36 | setup failed: RunnerError: pytest reported a usage error (exit 4) in /work/w/checkouts/scrapy- | | | | | | |
| scrapy 37 | ok | change | `scrapy/http/request/__init__.py::Request._set_url` | 1 / 24 | 3+3 / ✓ / ✓ | 10+3 / ✓ / ✓ | 4+3 / ✓ / ✓ |
| scrapy 38 | not reproducible: fixed: failed (v3: all requirements except: dropped pager==3.3 pywin32==227 SOAP | | | | | | |
| scrapy 39 | ok | change | `(module level)` | - / 26 | 9+0 / ✗ / ✗ | 6+0 / ✗ / ✗ | 7+0 / ✗ / ✗ |
| scrapy 40 | ok | change | `scrapy/exporters.py::PythonItemExporter._serialize_value` | 2 / 4 | 4+4 / ✓ / ✓ | 4+0 / ✗ / ✗ | 7+0 / ✗ / ✗ |
| thefuck 1 | ok | change | `thefuck/rules/pip_unknown_command.py::get_new_command` | 1 / 1 | 1+4 / ✓ / ✓ | 7+4 / ✓ / ✓ | 3+4 / ✓ / ✓ |
| thefuck 2 | not reproducible: buggy: passed (all requirements) | | | | | | |
| thefuck 3 | ok | change | `thefuck/shells/fish.py::Fish.info` | 1 / 1 | 1+3 / ✓ / ✓ | 6+3 / ✓ / ✓ | 2+3 / ✓ / ✓ |
| thefuck 4 | ok | change | `thefuck/shells/fish.py::_get_aliases` | 2 / 6 | 2+5 / ✓ / ✗ | 6+3 / ✗ / ✗ | 5+5 / ✓ / ✗ |
| thefuck 5 | ok | change | `thefuck/rules/git_push.py::match` | 2 / 4 | 4+2 / ✓ / ✗ | 10+2 / ✓ / ✗ | 4+2 / ✓ / ✗ |
| thefuck 6 | not reproducible: buggy: passed (all requirements) | | | | | | |
| thefuck 7 | not reproducible: buggy: passed (all requirements) | | | | | | |
| thefuck 8 | ok | change | `thefuck/rules/dnf_no_such_command.py::_get_operations thefuck/rules/dnf_no_such_command.py::_parse_operations` | 1 / 1 | 3+4 / ✓ / ✗ | 6+4 / ✓ / ✗ | 3+4 / ✓ / ✗ |
| thefuck 9 | ok | change | `thefuck/rules/git_push.py::get_new_command` | 1 / 12 | 3+6 / ✓ / ✓ | 12+6 / ✓ / ✓ | 6+6 / ✓ / ✓ |
| thefuck 10 | ok | change | `thefuck/rules/man.py::get_new_command` | 2 / 5 | 3+5 / ✓ / ✗ | 6+5 / ✓ / ✗ | 3+5 / ✓ / ✗ |
| thefuck 11 | not reproducible: fixed: failed (all requirements) | | | | | | |
| thefuck 12 | ok | change | `thefuck/rules/no_command.py::match` | 177 / - | 7+0 / ✗ / ✗ | 5+0 / ✗ / ✗ | 5+0 / ✗ / ✗ |
| thefuck 13 | ok | change | `thefuck/rules/git_branch_exists.py::match` | 8 / 5 | 4+2 / ✗ / ✗ | 12+2 / ✗ / ✗ | 6+2 / ✗ / ✗ |
| thefuck 14 | ok | change | `thefuck/shells/fish.py::Fish._get_overridden_aliases` | 1 / 1 | 1+3 / ✓ / ✓ | 5+3 / ✓ / ✓ | 2+3 / ✓ / ✓ |
| thefuck 15 | ok | change | `thefuck/rules/git_add.py::get_new_command thefuck/rules/git_add.py::match` | 2 / 1 | 4+3 / ✓ / ✓ | 8+3 / ✓ / ✓ | 4+3 / ✓ / ✓ |
| thefuck 16 | ok | change+insert | `thefuck/shells/bash.py::Bash.app_alias thefuck/shells/fish.py::Fish.app_alias thefuck/shells/zsh.py::Zsh.app_alias thefuck/types.py::CorrectedCommand.run` | 1 / 1 | 2+3 / ✓ / ✓ | 6+3 / ✓ / ✓ | 2+3 / ✓ / ✓ |
| thefuck 17 | ok | change | `thefuck/shells/bash.py::Bash.app_alias thefuck/shells/bash.py::Bash.get_aliases thefuck/shells/zsh.py::Zsh.get_aliases` | 1 / 1 | 2+3 / ✗ / ✗ | 6+0 / ✓ / ✗ | 2+3 / ✗ / ✗ |
| thefuck 18 | ok | insert | `thefuck/rules/sudo.py::match` | 2 / 5 | 2+3 / ✓ / ✓ | 8+3 / ✓ / ✓ | 5+3 / ✓ / ✓ |
| thefuck 19 | ok | change | `thefuck/rules/git_push_force.py::get_new_command` | 1 / 1 | 2+1 / ✓ / ✓ | 8+1 / ✓ / ✓ | 4+1 / ✓ / ✓ |
| thefuck 20 | not reproducible: buggy: passed (all requirements) | | | | | | |
| thefuck 21 | ok | change | `thefuck/rules/git_fix_stash.py::match` | 1 / 1 | 1+1 / ✓ / ✓ | 8+1 / ✓ / ✓ | 3+1 / ✓ / ✓ |
| thefuck 22 | ok | change | `thefuck/types.py::SortedCorrectedCommandsSequence._realise` | 4 / 15 | 7+0 / ✗ / ✗ | 3+0 / ✗ / ✗ | 5+0 / ✗ / ✗ |
| thefuck 23 | ok | change | `thefuck/utils.py::cache.<locals>._cache` | 1 / 8 | 2+3 / ✓ / ✗ | 4+3 / ✓ / ✗ | 3+3 / ✓ / ✗ |
| thefuck 24 | ok | change | `thefuck/types.py::SortedCorrectedCommandsSequence._get_first_two_unique thefuck/types.py::SortedCorrectedCommandsSequence._remove_duplicates` | 258 / 14 | 1+0 / ✗ / ✗ | 1+0 / ✗ / ✗ | 1+0 / ✗ / ✗ |
| thefuck 25 | not reproducible: buggy: passed (all requirements) | | | | | | |
| thefuck 26 | ok | change | `thefuck/rules/vagrant_up.py::get_new_command` | 1 / 2 | 1+3 / ✓ / ✓ | 2+3 / ✓ / ✓ | 1+3 / ✓ / ✓ |
| thefuck 27 | not reproducible: buggy: passed (all requirements) | | | | | | |
| thefuck 28 | ok | change | `thefuck/rules/fix_file.py::get_new_command` | 1 / 2 | 6+0 / ✓ / ✗ | 4+0 / ✓ / ✗ | 4+0 / ✓ / ✗ |
| thefuck 29 | ok | change | `thefuck/types.py::Settings.update` | 1 / 1 | 1+3 / ✓ / ✓ | 1+3 / ✓ / ✓ | 1+3 / ✓ / ✓ |
| thefuck 30 | ok | change | `thefuck/rules/fix_file.py::match` | 1 / 1 | 2+2 / ✓ / ✓ | 4+2 / ✓ / ✓ | 2+2 / ✓ / ✓ |
| thefuck 31 | not reproducible: buggy: passed (all requirements) | | | | | | |
| thefuck 32 | ok | change | `thefuck/rules/ls_lah.py::match` | 1 / 1 | 17+0 / ✓ / ✗ | 6+0 / ✓ / ✗ | 12+0 / ✓ / ✗ |
| tornado 1 | ok | change | `tornado/websocket.py::WebSocketHandler.set_nodelay` | 1 / 2 | 0+1 / ✗ / ✗ | 0+1 / ✗ / ✗ | 0+1 / ✗ / ✗ |
| tornado 2 | ok | change | `tornado/http1connection.py::HTTP1Connection.write_headers` | 124 / 22 | 6+0 / ✗ / ✗ | 10+7 / ✗ / ✗ | 31+0 / ✗ / ✗ |
| tornado 3 | not reproducible: buggy: passed (v3: all requirements except: dropped unittest) | | | | | | |
| tornado 4 | ok | change | `(module level)` | - / 3 | 6+4 / ✗ / ✗ | 10+7 / ✗ / ✗ | 18+7 / ✗ / ✗ |
| tornado 5 | ok | change | `tornado/ioloop.py::PeriodicCallback._update_next` | 2 / 7 | 5+1 / ✓ / ✗ | 4+1 / ✓ / ✗ | 3+1 / ✓ / ✗ |
| tornado 6 | ok | change+insert | `tornado/platform/asyncio.py::BaseAsyncIOLoop.close tornado/platform/asyncio.py::BaseAsyncIOLoop.initialize` | 11 / 31 | 8+0 / ✗ / ✗ | 3+0 / ✗ / ✗ | 3+0 / ✗ / ✗ |
| tornado 7 | ok | change | `tornado/ioloop.py::IOLoop.run_in_executor` | 5 / 62 | 0+1 / ✗ / ✗ | 0+1 / ✗ / ✗ | 0+1 / ✗ / ✗ |
| tornado 8 | ok | insert | `tornado/websocket.py::WebSocketProtocol13.accept_connection` | 41 / 348 | 7+6 / ✗ / ✗ | 12+6 / ✗ / ✗ | 33+0 / ✗ / ✗ |
| tornado 9 | ok | insert | `tornado/httputil.py::url_concat` | 1 / 5 | 1+4 / ✓ / ✓ | 1+4 / ✓ / ✓ | 1+4 / ✓ / ✓ |
| tornado 10 | ok | insert | `tornado/web.py::RequestHandler.finish tornado/websocket.py::WebSocketHandler.on_connection_close` | 50 / 276 | 0+1 / ✗ / ✗ | 0+1 / ✗ / ✗ | 0+1 / ✗ / ✗ |
| tornado 11 | ok | change | `tornado/http1connection.py::HTTP1Connection._read_body` | 50 / 60 | 5+6 / ✗ / ✗ | 13+6 / ✗ / ✗ | 31+0 / ✗ / ✗ |
| tornado 12 | ok | change | `tornado/auth.py::FacebookGraphMixin._on_access_token tornado/auth.py::FacebookGraphMixin.facebook_request` | - / - | nondeterministic | nondeterministic | nondeterministic |
| tornado 13 | ok | change | `tornado/http1connection.py::HTTP1Connection._can_keep_alive` | 26 / 205 | 0+1 / ✗ / ✗ | 0+1 / ✗ / ✗ | 0+1 / ✗ / ✗ |
| tornado 14 | ok | change | `tornado/ioloop.py::IOLoop.initialize` | 4 / 1 | 3+4 / ✓ / ✓ | 8+4 / ✓ / ✓ | 4+4 / ✓ / ✓ |
| tornado 15 | ok | change+insert | `tornado/web.py::StaticFileHandler.validate_absolute_path` | 5 / 23 | 9+6 / ✗ / ✗ | 12+6 / ✗ / ✗ | 28+6 / ✗ / ✗ |
| tornado 16 | ok | insert | `tornado/gen.py::WaitIterator.__init__ tornado/gen.py::WaitIterator.next` | 4 / 8 | 0+1 / ✗ / ✗ | 0+1 / ✗ / ✗ | 0+1 / ✗ / ✗ |
| tqdm 1 | ok | change | `tqdm/contrib/__init__.py::tenumerate` | 1 / 5 | 3+4 / ✓ / ✓ | 8+4 / ✓ / ✓ | 9+4 / ✓ / ✓ |
| tqdm 2 | ok | change | `tqdm/std.py::tqdm.format_meter tqdm/utils.py::disp_trim` | 6 / 26 | 8+8 / ✓ / ✓ | 8+8 / ✓ / ✓ | 8+8 / ✓ / ✓ |
| tqdm 3 | ok | insert | `tqdm/_tqdm.py::tqdm.__len__` | 1 / - | 9+8 / ✗ / ✗ | 28+8 / ✗ / ✗ | 30+0 / ✓ / ✗ |
| tqdm 4 | ok | change | `tqdm/_tqdm.py::tqdm.format_meter` | 8 / 1 | 3+2 / ✓ / ✓ | 13+2 / ✓ / ✓ | 4+2 / ✓ / ✓ |
| tqdm 5 | ok | change | `tqdm/_tqdm.py::tqdm.__init__` | 18 / 11 | 10+7 / ✓ / ✓ | 9+1 / ✗ / ✗ | 30+0 / ✗ / ✗ |
| tqdm 6 | ok | change | `tqdm/_tqdm.py::tqdm.__len__` | 1 / 11 | 5+1 / ✗ / ✗ | 4+0 / ✓ / ✗ | 6+1 / ✗ / ✗ |
| tqdm 7 | ok | change | `(module level)` | - / - | 4+0 / ✗ / ✗ | 4+0 / ✗ / ✗ | 5+0 / ✗ / ✗ |
| tqdm 8 | ok | change | `tqdm/_tqdm.py::tqdm.format_meter` | 3 / 2 | 3+8 / ✓ / ✓ | 10+8 / ✓ / ✓ | 7+8 / ✓ / ✓ |
| tqdm 9 | ok | change | `tqdm/_tqdm.py::format_sizeof tqdm/_tqdm.py::tqdm.__init__ tqdm/_tqdm.py::tqdm.__len__` | 1 / 3 | 3+4 / ✓ / ✓ | 9+4 / ✓ / ✓ | 7+4 / ✓ / ✓ |
| youtube-dl 1 | ok | change | `youtube_dl/utils.py::_match_one` | 1 / 35 | 2+6 / ✓ / ✗ | 24+6 / ✓ / ✗ | 24+6 / ✓ / ✗ |
| youtube-dl 2 | ok | change | `youtube_dl/extractor/common.py::InfoExtractor._parse_mpd_formats` | 1 / 125 | 5+0 / ✓ / ✗ | 30+12 / ✓ / ✗ | 30+12 / ✓ / ✗ |
| youtube-dl 3 | ok | change | `youtube_dl/utils.py::unescapeHTML` | 2 / 20 | 2+4 / ✓ / ✗ | 7+4 / ✓ / ✗ | 6+4 / ✓ / ✗ |
| youtube-dl 4 | ok | change | `youtube_dl/jsinterp.py::JSInterpreter.interpret_expression` | 4 / 2 | 3+9 / ✓ / ✗ | 13+9 / ✓ / ✗ | 4+9 / ✓ / ✗ |
| youtube-dl 5 | ok | change | `youtube_dl/utils.py::unified_timestamp` | 1 / 3 | 3+9 / ✓ / ✓ | 16+9 / ✓ / ✓ | 16+9 / ✓ / ✓ |
| youtube-dl 6 | ok | change | `youtube_dl/utils.py::dfxp2srt youtube_dl/utils.py::parse_dfxp_time_expr` | 1 / 2 | 1+2 / ✓ / ✓ | 1+2 / ✓ / ✓ | 1+2 / ✓ / ✓ |
| youtube-dl 7 | ok | change | `youtube_dl/utils.py::js_to_json.<locals>.fix_kv` | 2 / 6 | 1+3 / ✓ / ✓ | 4+3 / ✓ / ✓ | 4+3 / ✓ / ✓ |
| youtube-dl 8 | ok | change | `youtube_dl/YoutubeDL.py::YoutubeDL.build_format_selector.<locals>._parse_format_selection` | 15 / 100 | 4+7 / ✓ / ✓ | 32+0 / ✗ / ✗ | 14+7 / ✓ / ✓ |
| youtube-dl 9 | ok | change | `youtube_dl/YoutubeDL.py::YoutubeDL.build_format_selector.<locals>._parse_format_selection` | 15 / 4 | 1+12 / ✗ / ✗ | 31+0 / ✗ / ✗ | 31+0 / ✗ / ✗ |
| youtube-dl 10 | ok | change | `youtube_dl/utils.py::js_to_json` | 1 / - | 16+0 / ✓ / ✗ | 18+3 / ✓ / ✗ | 16+3 / ✓ / ✗ |
| youtube-dl 11 | ok | change | `youtube_dl/utils.py::str_to_int` | 1 / 1 | 1+2 / ✓ / ✓ | 3+2 / ✓ / ✓ | 3+2 / ✓ / ✓ |
| youtube-dl 12 | ok | change | `youtube_dl/YoutubeDL.py::YoutubeDL._build_format_filter` | 2 / 1 | 2+9 / ✗ / ✗ | 24+15 / ✗ / ✗ | 19+15 / ✗ / ✗ |
| youtube-dl 13 | ok | change | `youtube_dl/utils.py::urljoin` | 1 / 5 | 1+3 / ✓ / ✓ | 20+3 / ✓ / ✓ | 20+3 / ✓ / ✓ |
| youtube-dl 14 | ok | change | `youtube_dl/extractor/youtube.py::YoutubeIE._extract_chapters youtube_dl/extractor/youtube.py::YoutubeIE._real_extract` | 2469 / - | 3+0 / ✗ / ✗ | 2+0 / ✗ / ✗ | 2+0 / ✗ / ✗ |
| youtube-dl 15 | ok | change | `youtube_dl/utils.py::js_to_json` | 1 / - | 3+6 / ✓ / ✗ | 24+6 / ✓ / ✗ | 20+6 / ✓ / ✗ |
| youtube-dl 16 | ok | change | `youtube_dl/postprocessor/ffmpeg.py::FFmpegSubtitlesConvertorPP.run youtube_dl/utils.py::dfxp2srt` | 1 / 2 | 1+6 / ✓ / ✓ | 2+6 / ✓ / ✓ | 2+6 / ✓ / ✓ |
| youtube-dl 17 | ok | insert | `youtube_dl/utils.py::cli_bool_option` | 1 / 1 | 1+2 / ✓ / ✓ | 7+2 / ✓ / ✓ | 7+2 / ✓ / ✓ |
| youtube-dl 18 | ok | change | `youtube_dl/YoutubeDL.py::YoutubeDL.process_ie_result` | 16 / 37 | 5+7 / ✓ / ✓ | 21+7 / ✓ / ✓ | 7+7 / ✓ / ✓ |
| youtube-dl 19 | ok | change | `youtube_dl/YoutubeDL.py::YoutubeDL.prepare_filename` | 1 / 33 | 1+10 / ✓ / ✗ | 28+10 / ✓ / ✗ | 31+10 / ✓ / ✗ |
| youtube-dl 20 | ok | change | `youtube_dl/utils.py::get_elements_by_attribute` | 2 / - | 1+4 / ✓ / ✗ | 5+4 / ✓ / ✗ | 5+4 / ✓ / ✗ |
| youtube-dl 21 | ok | change | `youtube_dl/utils.py::urljoin` | 1 / 3 | 1+3 / ✓ / ✓ | 2+3 / ✓ / ✓ | 2+3 / ✓ / ✓ |
| youtube-dl 22 | ok | change | `youtube_dl/utils.py::_match_one` | 2 / 45 | 4+5 / ✓ / ✗ | 30+4 / ✗ / ✗ | 17+5 / ✓ / ✗ |
| youtube-dl 23 | ok | change | `youtube_dl/utils.py::js_to_json youtube_dl/utils.py::js_to_json.<locals>.fix_kv` | 1 / 5 | 3+4 / ✓ / ✗ | 9+4 / ✓ / ✗ | 9+4 / ✓ / ✗ |
| youtube-dl 24 | ok | change | `youtube_dl/utils.py::_match_one` | 2 / 44 | 7+6 / ✓ / ✓ | 31+4 / ✗ / ✗ | 17+6 / ✓ / ✓ |
| youtube-dl 25 | ok | change | `youtube_dl/utils.py::js_to_json.<locals>.fix_kv` | 2 / 18 | 3+6 / ✓ / ✗ | 9+6 / ✓ / ✗ | 6+6 / ✓ / ✗ |
| youtube-dl 26 | ok | change | `youtube_dl/utils.py::js_to_json` | 1 / - | 3+4 / ✓ / ✗ | 8+4 / ✓ / ✗ | 6+4 / ✓ / ✗ |
| youtube-dl 27 | ok | change | `youtube_dl/utils.py::parse_dfxp_time_expr` | 1 / 1 | 1+4 / ✓ / ✓ | 7+4 / ✓ / ✓ | 7+4 / ✓ / ✓ |
| youtube-dl 28 | ok | change | `youtube_dl/utils.py::_htmlentity_transform` | 1 / 10 | 1+4 / ✓ / ✗ | 6+4 / ✓ / ✗ | 5+4 / ✓ / ✗ |
| youtube-dl 29 | ok | change | `youtube_dl/utils.py::unified_strdate` | 1 / 50 | 1+9 / ✓ / ✓ | 11+9 / ✓ / ✓ | 11+9 / ✓ / ✓ |
| youtube-dl 30 | ok | insert | `youtube_dl/YoutubeDL.py::YoutubeDL.build_format_selector.<locals>._build_selector_function` | 7 / 154 | 1+9 / ✗ / ✗ | 33+0 / ✗ / ✗ | 21+9 / ✗ / ✗ |
| youtube-dl 31 | ok | change | `youtube_dl/extractor/minhateca.py::MinhatecaIE._real_extract youtube_dl/utils.py::parse_duration` | 1 / 6 | 1+4 / ✓ / ✗ | 21+4 / ✓ / ✗ | 21+4 / ✓ / ✗ |
| youtube-dl 32 | ok | change | `youtube_dl/extractor/npo.py::NPOIE._get_info youtube_dl/utils.py::strip_jsonp` | 1 / 1 | 1+1 / ✓ / ✓ | 2+1 / ✓ / ✓ | 2+1 / ✓ / ✓ |
| youtube-dl 33 | ok | change | `youtube_dl/extractor/drtv.py::DRTVIE._real_extract youtube_dl/utils.py::parse_iso8601` | 1 / 3 | 1+5 / ✓ / ✗ | 4+5 / ✓ / ✗ | 4+5 / ✓ / ✗ |
| youtube-dl 34 | ok | change | `youtube_dl/utils.py::ExtractorError.__init__ youtube_dl/utils.py::js_to_json` | 1 / - | 2+4 / ✓ / ✗ | 2+4 / ✓ / ✗ | 2+4 / ✓ / ✗ |
| youtube-dl 35 | ok | change+insert | `youtube_dl/extractor/arte.py::ArteTVPlus7IE._extract_from_json_url youtube_dl/utils.py::unified_strdate` | 1 / 18 | 1+9 / ✓ / ✗ | 6+9 / ✓ / ✗ | 6+9 / ✓ / ✗ |
| youtube-dl 36 | ok | change | `(module level)` | - / - | 4+2 / ✗ / ✗ | 3+2 / ✗ / ✗ | 3+2 / ✗ / ✗ |
| youtube-dl 37 | ok | change | `youtube_dl/utils.py::uppercase_escape` | 1 / 3 | 1+3 / ✓ / ✗ | 2+3 / ✓ / ✗ | 2+3 / ✓ / ✗ |
| youtube-dl 38 | ok |  | `(module level)` | - / - | - | - | - |
| youtube-dl 39 | ok |  | `(module level)` | - / - | - | - | - |
| youtube-dl 40 | ok |  | `(module level)` | - / - | - | - | - |
| youtube-dl 41 | ok | change | `youtube_dl/utils.py::unified_strdate` | 1 / 2 | 1+8 / ✓ / ✓ | 5+8 / ✓ / ✓ | 5+8 / ✓ / ✓ |
| youtube-dl 42 | ok |  | `(module level)` | - / - | - | - | - |
| youtube-dl 43 | ok | change | `youtube_dl/utils.py::url_basename` | 1 / 1 | 1+3 / ✓ / ✓ | 6+3 / ✓ / ✓ | 6+3 / ✓ / ✓ |
