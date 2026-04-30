"""runtime — Hull carrier implementations.

Two carriers, one shared HTTP bridge:
- subprocess_mode — spawned by ShellServer
- container_mode  — Docker ENTRYPOINT
- hull_adapter    — HullHttpHandlerBase (owns do_GET/do_POST/_read_json/_respond)
"""
