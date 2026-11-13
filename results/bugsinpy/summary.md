# qdebug on BugsInPy

96 bugs attempted, 87 reproduced on this machine. GroundTruthOracle, noise 0, assumed ε = 0.1. Spectrum: the bug's test file(s) only.

## Setup outcome

| status | bugs |
|---|---|
| no trace | 6 |
| nondeterministic | 1 |
| not reproducible | 9 |
| ok | 80 |

## Per strategy (bugs with a completed session)

| strategy | sessions | function found | found before zoom | func. Q (mean / median) | line Q (mean) | true line in region | region size |
|---|---|---|---|---|---|---|---|
| infogain | 80 | 62% | 65% | 7.9 / 3 | 4.5 | 39% | 1.6 |
| divide | 80 | 62% | 64% | 8.4 / 4.5 | 4.6 | 40% | 1.6 |
| topdown | 80 | 64% | 65% | 7.9 / 4 | 5.0 | 40% | 1.3 |

## infogain against SBFL (Ochiai on the same spectrum)

The same 80 sessions. SBFL "top-k" means the buggy function or line is among the k most suspicious; qdebug reports one function and a region of 1.6 lines on average.

| | qdebug | SBFL top-1 | SBFL top-3 | SBFL top-5 |
|---|---|---|---|---|
| buggy function | 50 / 80 | 46 / 80 | 58 / 80 | 60 / 80 |
| buggy line | 31 / 80 | 18 / 80 | 30 / 80 | 39 / 80 |

By tree size: 50 of 68 failing tests with fewer than 100 calls, 0 of 12 with 100 or more (median tree: 9.5 calls).

## Per project

| project | attempted | reproduced | infogain: found / line | divide: found / line | topdown: found / line |
|---|---|---|---|---|---|
| PySnooper | 3 | 3 | 0 / 0 of 2 | 0 / 0 of 2 | 0 / 0 of 2 |
| cookiecutter | 4 | 3 | 2 / 1 of 3 | 2 / 1 of 3 | 2 / 1 of 3 |
| httpie | 5 | 5 | 1 / 0 of 4 | 0 / 0 of 4 | 0 / 0 of 4 |
| thefuck | 32 | 24 | 19 / 13 of 24 | 18 / 13 of 24 | 18 / 13 of 24 |
| tqdm | 9 | 9 | 4 / 4 of 8 | 4 / 4 of 8 | 4 / 4 of 8 |
| youtube-dl | 43 | 43 | 24 / 13 of 39 | 26 / 14 of 39 | 27 / 14 of 39 |

## Per bug

| bug | status | patch | buggy function(s) | SBFL func / line rank | infogain: Q / found / line | divide: Q / found / line | topdown: Q / found / line |
|---|---|---|---|---|---|---|---|
| PySnooper 1 | ok | change+insert | `pysnooper/tracer.py::FileWriter.write pysnooper/tracer.py::get_source_from_frame` | 13 / - | 3+4 / ✗ / ✗ | 2+4 / ✗ / ✗ | 4+4 / ✗ / ✗ |
| PySnooper 2 | ok |  | `(module level)` | - / - | - | - | - |
| PySnooper 3 | ok | change | `pysnooper/pysnooper.py::get_write_function` | 1 / - | 3+4 / ✗ / ✗ | 5+4 / ✗ / ✗ | 4+4 / ✗ / ✗ |
| cookiecutter 1 | ok | change | `cookiecutter/generate.py::generate_context` | 1 / 4 | 1+3 / ✓ / ✓ | 1+3 / ✓ / ✓ | 1+3 / ✓ / ✓ |
| cookiecutter 2 | ok | change | `cookiecutter/hooks.py::find_hook cookiecutter/hooks.py::run_hook` | 1 / 1 | 3+4 / ✓ / ✗ | 3+4 / ✓ / ✗ | 3+4 / ✓ / ✗ |
| cookiecutter 3 | not reproducible: fixed: failed (all requirements) | | | | | | |
| cookiecutter 4 | ok | change+insert | `cookiecutter/generate.py::generate_files cookiecutter/hooks.py::run_hook cookiecutter/hooks.py::run_script cookiecutter/hooks.py::run_script_with_context` | 11 / 27 | 0+5 / ✗ / ✗ | 0+5 / ✗ / ✗ | 0+5 / ✗ / ✗ |
| httpie 1 | ok | change | `httpie/downloads.py::get_unique_filename` | - / - | no trace | no trace | no trace |
| httpie 2 | ok | change+insert | `httpie/client.py::get_response httpie/core.py::main` | 1 / 5 | 9+1 / ✗ / ✗ | 5+1 / ✗ / ✗ | 1+4 / ✗ / ✗ |
| httpie 3 | ok | insert | `httpie/sessions.py::Session.update_headers` | 10 / 251 | 21+6 / ✗ / ✗ | 5+2 / ✗ / ✗ | 3+6 / ✗ / ✗ |
| httpie 4 | ok | change | `httpie/models.py::HTTPRequest.headers` | 34 / 453 | 27+5 / ✓ / ✗ | 9+6 / ✗ / ✗ | 3+6 / ✗ / ✗ |
| httpie 5 | ok | change | `httpie/cli.py::KeyValueType.__call__` | 2 / 19 | 0+2 / ✗ / ✗ | 1+1 / ✗ / ✗ | 1+1 / ✗ / ✗ |
| thefuck 1 | ok | change | `thefuck/rules/pip_unknown_command.py::get_new_command` | 1 / 1 | 1+4 / ✓ / ✓ | 2+4 / ✓ / ✓ | 2+4 / ✓ / ✓ |
| thefuck 2 | not reproducible: buggy: passed (all requirements) | | | | | | |
| thefuck 3 | ok | change | `thefuck/shells/fish.py::Fish.info` | 1 / 1 | 1+3 / ✓ / ✓ | 1+3 / ✓ / ✓ | 1+3 / ✓ / ✓ |
| thefuck 4 | ok | change | `thefuck/shells/fish.py::_get_aliases` | 2 / 6 | 4+5 / ✓ / ✗ | 4+5 / ✓ / ✗ | 6+5 / ✓ / ✗ |
| thefuck 5 | ok | change | `thefuck/rules/git_push.py::match` | 2 / 4 | 4+4 / ✓ / ✗ | 4+4 / ✓ / ✗ | 5+4 / ✓ / ✗ |
| thefuck 6 | not reproducible: buggy: passed (all requirements) | | | | | | |
| thefuck 7 | not reproducible: buggy: passed (all requirements) | | | | | | |
| thefuck 8 | ok | change | `thefuck/rules/dnf_no_such_command.py::_get_operations thefuck/rules/dnf_no_such_command.py::_parse_operations` | 1 / 1 | 2+3 / ✓ / ✗ | 3+3 / ✓ / ✗ | 6+3 / ✓ / ✗ |
| thefuck 9 | ok | change | `thefuck/rules/git_push.py::get_new_command` | 1 / 12 | 5+6 / ✓ / ✓ | 6+6 / ✓ / ✓ | 8+6 / ✓ / ✓ |
| thefuck 10 | ok | change | `thefuck/rules/man.py::get_new_command` | 2 / 5 | 3+5 / ✓ / ✗ | 3+5 / ✓ / ✗ | 3+5 / ✓ / ✗ |
| thefuck 11 | not reproducible: fixed: failed (all requirements) | | | | | | |
| thefuck 12 | ok | change | `thefuck/rules/no_command.py::match` | 177 / - | 0+2 / ✗ / ✗ | 0+2 / ✗ / ✗ | 0+2 / ✗ / ✗ |
| thefuck 13 | ok | change | `thefuck/rules/git_branch_exists.py::match` | 7 / 5 | 6+2 / ✗ / ✗ | 6+2 / ✗ / ✗ | 7+2 / ✗ / ✗ |
| thefuck 14 | ok | change | `thefuck/shells/fish.py::Fish._get_overridden_aliases` | 1 / 1 | 1+2 / ✓ / ✓ | 1+2 / ✓ / ✓ | 1+2 / ✓ / ✓ |
| thefuck 15 | ok | change | `thefuck/rules/git_add.py::get_new_command thefuck/rules/git_add.py::match` | 2 / 1 | 4+2 / ✓ / ✓ | 3+2 / ✓ / ✓ | 4+2 / ✓ / ✓ |
| thefuck 16 | ok | change+insert | `thefuck/shells/bash.py::Bash.app_alias thefuck/shells/fish.py::Fish.app_alias thefuck/shells/zsh.py::Zsh.app_alias thefuck/types.py::CorrectedCommand.run` | 2 / 2 | 2+3 / ✓ / ✓ | 2+3 / ✓ / ✓ | 2+3 / ✓ / ✓ |
| thefuck 17 | ok | change | `thefuck/shells/bash.py::Bash.app_alias thefuck/shells/bash.py::Bash.get_aliases thefuck/shells/zsh.py::Zsh.get_aliases` | 1 / 1 | 3+5 / ✓ / ✓ | 3+5 / ✓ / ✓ | 2+11 / ✓ / ✓ |
| thefuck 18 | ok | insert | `thefuck/rules/sudo.py::match` | 2 / 5 | 3+2 / ✓ / ✓ | 4+2 / ✓ / ✓ | 4+2 / ✓ / ✓ |
| thefuck 19 | ok | change | `thefuck/rules/git_push_force.py::get_new_command` | 1 / 1 | 2+1 / ✓ / ✓ | 4+1 / ✓ / ✓ | 4+1 / ✓ / ✓ |
| thefuck 20 | not reproducible: buggy: passed (all requirements) | | | | | | |
| thefuck 21 | ok | change | `thefuck/rules/git_fix_stash.py::match` | 1 / 1 | 2+1 / ✓ / ✓ | 3+1 / ✓ / ✓ | 4+1 / ✓ / ✓ |
| thefuck 22 | ok | change | `thefuck/types.py::SortedCorrectedCommandsSequence._realise` | 4 / 15 | 4+8 / ✗ / ✗ | 2+2 / ✗ / ✗ | 2+6 / ✗ / ✗ |
| thefuck 23 | ok | change | `thefuck/utils.py::cache.<locals>._cache` | 1 / 8 | 3+3 / ✓ / ✗ | 3+3 / ✓ / ✗ | 3+3 / ✓ / ✗ |
| thefuck 24 | ok | change | `thefuck/types.py::SortedCorrectedCommandsSequence._get_first_two_unique thefuck/types.py::SortedCorrectedCommandsSequence._remove_duplicates` | 258 / 14 | 1+1 / ✗ / ✗ | 1+1 / ✗ / ✗ | 1+1 / ✗ / ✗ |
| thefuck 25 | not reproducible: buggy: passed (all requirements) | | | | | | |
| thefuck 26 | ok | change | `thefuck/rules/vagrant_up.py::get_new_command` | 1 / 2 | 1+3 / ✓ / ✓ | 1+3 / ✓ / ✓ | 1+3 / ✓ / ✓ |
| thefuck 27 | not reproducible: buggy: passed (all requirements) | | | | | | |
| thefuck 28 | ok | change | `thefuck/rules/fix_file.py::get_new_command` | 1 / 2 | 4+44 / ✗ / ✗ | 4+32 / ✗ / ✗ | 2+4 / ✗ / ✗ |
| thefuck 29 | ok | change | `thefuck/types.py::Settings.update` | 1 / 1 | 1+2 / ✓ / ✓ | 1+2 / ✓ / ✓ | 1+2 / ✓ / ✓ |
| thefuck 30 | ok | change | `thefuck/rules/fix_file.py::match` | 1 / 1 | 2+2 / ✓ / ✓ | 2+2 / ✓ / ✓ | 3+2 / ✓ / ✓ |
| thefuck 31 | not reproducible: buggy: passed (all requirements) | | | | | | |
| thefuck 32 | ok | change | `thefuck/rules/ls_lah.py::match` | 1 / 1 | 4+0 / ✓ / ✗ | 5+5 / ✗ / ✗ | 5+5 / ✗ / ✗ |
| tqdm 1 | ok | change | `tqdm/contrib/__init__.py::tenumerate` | - / - | nondeterministic | nondeterministic | nondeterministic |
| tqdm 2 | ok | change | `tqdm/std.py::tqdm.format_meter tqdm/utils.py::disp_trim` | 6 / 26 | 8+8 / ✓ / ✓ | 8+8 / ✓ / ✓ | 8+8 / ✓ / ✓ |
| tqdm 3 | ok | insert | `tqdm/_tqdm.py::tqdm.__len__` | 1 / - | 10+5 / ✗ / ✗ | 30+5 / ✗ / ✗ | 24+4 / ✗ / ✗ |
| tqdm 4 | ok | change | `tqdm/_tqdm.py::tqdm.format_meter` | 8 / 1 | 4+3 / ✓ / ✓ | 4+3 / ✓ / ✓ | 6+4 / ✗ / ✗ |
| tqdm 5 | ok | change | `tqdm/_tqdm.py::tqdm.__init__` | 18 / 11 | 20+4 / ✗ / ✗ | 30+5 / ✗ / ✗ | 8+1 / ✗ / ✗ |
| tqdm 6 | ok | change | `tqdm/_tqdm.py::tqdm.__len__` | 1 / 11 | 3+4 / ✗ / ✗ | 3+4 / ✗ / ✗ | 3+3 / ✓ / ✓ |
| tqdm 7 | ok | change | `(module level)` | - / - | 5+8 / ✗ / ✗ | 4+6 / ✗ / ✗ | 4+6 / ✗ / ✗ |
| tqdm 8 | ok | change | `tqdm/_tqdm.py::tqdm.format_meter` | 3 / 2 | 7+7 / ✓ / ✓ | 7+7 / ✓ / ✓ | 10+7 / ✓ / ✓ |
| tqdm 9 | ok | change | `tqdm/_tqdm.py::format_sizeof tqdm/_tqdm.py::tqdm.__init__ tqdm/_tqdm.py::tqdm.__len__` | 1 / 3 | 8+4 / ✓ / ✓ | 7+4 / ✓ / ✓ | 9+4 / ✓ / ✓ |
| youtube-dl 1 | ok | change | `youtube_dl/utils.py::_match_one` | 1 / 35 | 24+6 / ✓ / ✗ | 24+6 / ✓ / ✗ | 24+6 / ✓ / ✗ |
| youtube-dl 2 | ok | change | `youtube_dl/extractor/common.py::InfoExtractor._parse_mpd_formats` | 1 / 292 | 13+4 / ✗ / ✗ | 9+1 / ✗ / ✗ | 2+1 / ✗ / ✗ |
| youtube-dl 3 | ok | change | `youtube_dl/utils.py::unescapeHTML` | 2 / 20 | 6+4 / ✓ / ✗ | 6+4 / ✓ / ✗ | 7+4 / ✓ / ✗ |
| youtube-dl 4 | ok | change | `youtube_dl/jsinterp.py::JSInterpreter.interpret_expression` | 4 / 2 | 6+3 / ✗ / ✗ | 5+3 / ✗ / ✗ | 13+8 / ✓ / ✗ |
| youtube-dl 5 | ok | change | `youtube_dl/utils.py::unified_timestamp` | 1 / 3 | 16+8 / ✓ / ✓ | 16+8 / ✓ / ✓ | 16+8 / ✓ / ✓ |
| youtube-dl 6 | ok | change | `youtube_dl/utils.py::dfxp2srt youtube_dl/utils.py::parse_dfxp_time_expr` | 1 / 2 | 1+2 / ✓ / ✓ | 1+2 / ✓ / ✓ | 1+2 / ✓ / ✓ |
| youtube-dl 7 | ok | change | `youtube_dl/utils.py::js_to_json.<locals>.fix_kv` | 2 / 6 | 4+3 / ✓ / ✓ | 4+3 / ✓ / ✓ | 4+3 / ✓ / ✓ |
| youtube-dl 8 | ok | change | `youtube_dl/YoutubeDL.py::YoutubeDL.build_format_selector.<locals>._parse_format_selection` | 75 / - | 34+0 / ✗ / ✗ | 30+7 / ✗ / ✗ | 30+14 / ✗ / ✗ |
| youtube-dl 9 | ok | change | `youtube_dl/YoutubeDL.py::YoutubeDL.build_format_selector.<locals>._parse_format_selection` | 76 / - | 30+10 / ✗ / ✗ | 30+10 / ✗ / ✗ | 30+14 / ✗ / ✗ |
| youtube-dl 10 | ok | change | `youtube_dl/utils.py::js_to_json` | 1 / - | 2+6 / ✗ / ✗ | 16+6 / ✗ / ✗ | 18+9 / ✗ / ✗ |
| youtube-dl 11 | ok | change | `youtube_dl/utils.py::str_to_int` | 1 / 1 | 1+2 / ✓ / ✓ | 3+2 / ✓ / ✓ | 3+2 / ✓ / ✓ |
| youtube-dl 12 | ok | change | `youtube_dl/YoutubeDL.py::YoutubeDL._build_format_filter` | 70 / - | 30+10 / ✗ / ✗ | 29+10 / ✗ / ✗ | 22+17 / ✗ / ✗ |
| youtube-dl 13 | ok | change | `youtube_dl/utils.py::urljoin` | 1 / 5 | 1+4 / ✓ / ✓ | 20+4 / ✓ / ✓ | 20+4 / ✓ / ✓ |
| youtube-dl 14 | ok | change | `youtube_dl/extractor/youtube.py::YoutubeIE._extract_chapters youtube_dl/extractor/youtube.py::YoutubeIE._real_extract` | 2469 / - | 3+6 / ✗ / ✗ | 2+4 / ✗ / ✗ | 1+4 / ✗ / ✗ |
| youtube-dl 15 | ok | change | `youtube_dl/utils.py::js_to_json` | 1 / - | 24+13 / ✗ / ✗ | 20+13 / ✗ / ✗ | 24+19 / ✗ / ✗ |
| youtube-dl 16 | ok | change | `youtube_dl/postprocessor/ffmpeg.py::FFmpegSubtitlesConvertorPP.run youtube_dl/utils.py::dfxp2srt` | 1 / 2 | 1+5 / ✓ / ✓ | 2+5 / ✓ / ✓ | 2+5 / ✓ / ✓ |
| youtube-dl 17 | ok | insert | `youtube_dl/utils.py::cli_bool_option` | 1 / 1 | 1+2 / ✓ / ✓ | 7+2 / ✓ / ✓ | 7+2 / ✓ / ✓ |
| youtube-dl 18 | ok | change | `youtube_dl/YoutubeDL.py::YoutubeDL.process_ie_result` | 124 / - | 34+0 / ✗ / ✗ | 30+5 / ✗ / ✗ | 21+6 / ✗ / ✗ |
| youtube-dl 19 | ok | change | `youtube_dl/YoutubeDL.py::YoutubeDL.prepare_filename` | 113 / - | 34+0 / ✗ / ✗ | 32+3 / ✗ / ✗ | 23+9 / ✗ / ✗ |
| youtube-dl 20 | ok | change | `youtube_dl/utils.py::get_elements_by_attribute` | 7 / - | 5+4 / ✓ / ✗ | 5+4 / ✓ / ✗ | 5+4 / ✓ / ✗ |
| youtube-dl 21 | ok | change | `youtube_dl/utils.py::urljoin` | 1 / 3 | 1+3 / ✓ / ✓ | 2+3 / ✓ / ✓ | 2+3 / ✓ / ✓ |
| youtube-dl 22 | ok | change | `youtube_dl/utils.py::_match_one` | 1 / 79 | 34+0 / ✗ / ✗ | 31+5 / ✓ / ✗ | 30+8 / ✓ / ✗ |
| youtube-dl 23 | ok | change | `youtube_dl/utils.py::js_to_json youtube_dl/utils.py::js_to_json.<locals>.fix_kv` | 1 / 5 | 9+4 / ✓ / ✗ | 9+4 / ✓ / ✗ | 9+4 / ✓ / ✗ |
| youtube-dl 24 | ok | change | `youtube_dl/utils.py::_match_one` | 1 / 73 | 34+0 / ✗ / ✗ | 31+6 / ✓ / ✓ | 30+6 / ✓ / ✓ |
| youtube-dl 25 | ok | change | `youtube_dl/utils.py::js_to_json.<locals>.fix_kv` | 2 / 18 | 6+5 / ✓ / ✗ | 6+5 / ✓ / ✗ | 9+5 / ✓ / ✗ |
| youtube-dl 26 | ok | change | `youtube_dl/utils.py::js_to_json` | 1 / - | 28+14 / ✗ / ✗ | 6+14 / ✗ / ✗ | 8+18 / ✗ / ✗ |
| youtube-dl 27 | ok | change | `youtube_dl/utils.py::parse_dfxp_time_expr` | 1 / 1 | 1+4 / ✓ / ✓ | 7+4 / ✓ / ✓ | 7+4 / ✓ / ✓ |
| youtube-dl 28 | ok | change | `youtube_dl/utils.py::_htmlentity_transform` | 1 / 10 | 5+4 / ✓ / ✗ | 5+4 / ✓ / ✗ | 6+4 / ✓ / ✗ |
| youtube-dl 29 | ok | change | `youtube_dl/utils.py::unified_strdate` | 1 / 50 | 1+9 / ✓ / ✓ | 11+9 / ✓ / ✓ | 11+9 / ✓ / ✓ |
| youtube-dl 30 | ok | insert | `youtube_dl/YoutubeDL.py::YoutubeDL.build_format_selector.<locals>._build_selector_function` | 66 / - | 33+1 / ✗ / ✗ | 30+4 / ✗ / ✗ | 30+8 / ✗ / ✗ |
| youtube-dl 31 | ok | change | `youtube_dl/extractor/minhateca.py::MinhatecaIE._real_extract youtube_dl/utils.py::parse_duration` | 1 / 6 | 1+4 / ✓ / ✗ | 21+4 / ✓ / ✗ | 21+4 / ✓ / ✗ |
| youtube-dl 32 | ok | change | `youtube_dl/extractor/npo.py::NPOIE._get_info youtube_dl/utils.py::strip_jsonp` | 1 / 1 | 1+1 / ✓ / ✓ | 2+1 / ✓ / ✓ | 2+1 / ✓ / ✓ |
| youtube-dl 33 | ok | change | `youtube_dl/extractor/drtv.py::DRTVIE._real_extract youtube_dl/utils.py::parse_iso8601` | 2 / 5 | 1+5 / ✓ / ✗ | 4+5 / ✓ / ✗ | 4+5 / ✓ / ✗ |
| youtube-dl 34 | ok | change | `youtube_dl/utils.py::ExtractorError.__init__ youtube_dl/utils.py::js_to_json` | 1 / - | 2+3 / ✓ / ✗ | 2+3 / ✓ / ✗ | 2+3 / ✓ / ✗ |
| youtube-dl 35 | ok | change+insert | `youtube_dl/extractor/arte.py::ArteTVPlus7IE._extract_from_json_url youtube_dl/utils.py::unified_strdate` | 1 / 18 | 1+8 / ✓ / ✗ | 6+8 / ✓ / ✗ | 6+8 / ✓ / ✗ |
| youtube-dl 36 | ok | change | `(module level)` | - / - | 4+4 / ✗ / ✗ | 3+1 / ✗ / ✗ | 1+1 / ✗ / ✗ |
| youtube-dl 37 | ok | change | `youtube_dl/utils.py::uppercase_escape` | 1 / 3 | 1+3 / ✓ / ✗ | 2+3 / ✓ / ✗ | 2+3 / ✓ / ✗ |
| youtube-dl 38 | ok |  | `(module level)` | - / - | - | - | - |
| youtube-dl 39 | ok |  | `(module level)` | - / - | - | - | - |
| youtube-dl 40 | ok |  | `(module level)` | - / - | - | - | - |
| youtube-dl 41 | ok | change | `youtube_dl/utils.py::unified_strdate` | 1 / 2 | 1+7 / ✓ / ✓ | 5+7 / ✓ / ✓ | 5+7 / ✓ / ✓ |
| youtube-dl 42 | ok |  | `(module level)` | - / - | - | - | - |
| youtube-dl 43 | ok | change | `youtube_dl/utils.py::url_basename` | 1 / 1 | 1+2 / ✓ / ✓ | 6+2 / ✓ / ✓ | 6+2 / ✓ / ✓ |
