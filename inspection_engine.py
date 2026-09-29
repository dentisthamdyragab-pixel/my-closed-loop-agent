import ast
import shlex
import logging

class InspectionEngine:
    """
    Implements static analysis for Python and Shell commands to provide defense-in-depth.
    As per Spec V2.4, this is a pre-filter and not the primary security boundary.
    """
    def __init__(self):
        # Forbidden Python calls and modules
        self.forbidden_calls = {'eval', 'exec', 'compile', '__import__', 'getattr', 'setattr', 'open'}
        self.forbidden_modules = {'os', 'subprocess', 'sys', 'shutil', 'socket', 'ctypes', 'importlib', 'pty'}

        # Shell hard-blocks (denylist)
        self.shell_denylist = {
            'rm', 'sudo', 'chmod', 'chown', 'mkfs', 'dd', 'curl', 'wget', 'nc', 'bash', 'sh'
        }

    def inspect_python(self, code: str) -> tuple[bool, str]:
        """
        Parses Python code and checks for forbidden AST nodes.
        Returns (is_safe, error_message).
        """
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, f"Syntax error: {e}"

        for node in ast.walk(tree):
            # Check for forbidden function calls
            if isinstance(node, ast.Call):
                func = node.func
                # Handle simple calls: func()
                if isinstance(func, ast.Name) and func.id in self.forbidden_calls:
                    return False, f"Forbidden call detected: {func.id}"
                # Handle attribute calls: module.func()
                if isinstance(func, ast.Attribute) and func.attr in self.forbidden_calls:
                    return False, f"Forbidden attribute call detected: {func.attr}"

            # Check for forbidden imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split('.')[0] in self.forbidden_modules:
                        return False, f"Forbidden module import: {alias.name}"

            if isinstance(node, ast.ImportFrom):
                if node.module and node.module.split('.')[0] in self.forbidden_modules:
                    return False, f"Forbidden module import from: {node.module}"

            # Check for dunder-chain access (__subclasses__, etc)
            if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
                return False, f"Forbidden dunder access: {node.attr}"

        return True, "Safe"

    def inspect_shell(self, command: str) -> tuple[bool, str]:
        """
        Tokenizes shell commands and checks against the hard-block denylist.
        Returns (is_safe, error_message).
        """
        try:
            tokens = shlex.split(command)
        except ValueError as e:
            return False, f"Shell tokenization error: {e}"

        for token in tokens:
            # Basic check for binary name in denylist
            # Note: This is a simple check; real-world would handle paths like /bin/rm
            cmd_name = token.split('/')[-1]
            if cmd_name in self.shell_denylist:
                return False, f"Forbidden shell command: {cmd_name}"

        return True, "Safe"

if __name__ == "__main__":
    engine = InspectionEngine()

    # Python Tests
    tests_py = [
        ("print('Hello')", True),
        ("eval('1+1')", False),
        ("import os", False),
        (""".__class__.__mro__[1].__subclasses__()""", False),
    ]

    print("Testing Python Inspection:")
    for code, expected in tests_py:
        safe, msg = engine.inspect_python(code)
        print(f"Code: {code} | Safe: {safe} | Expected: {expected} | Msg: {msg}")

    # Shell Tests
    tests_sh = [
        ("ls -la", True),
        ("rm -rf /", False),
        ("sudo apt update", False),
        ("cat /etc/passwd", True), # Allowed by denylist, restricted by sandbox
    ]

    print("\nTesting Shell Inspection:")
    for cmd, expected in tests_sh:
        safe, msg = engine.inspect_shell(cmd)
        print(f"Cmd: {cmd} | Safe: {safe} | Expected: {expected} | Msg: {msg}")
