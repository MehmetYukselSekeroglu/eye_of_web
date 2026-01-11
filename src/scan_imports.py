import os
import ast
import sys
import stdlib_list


def get_stdlib():
    try:
        return set(stdlib_list.stdlib_list("3.8")) | set(sys.builtin_module_names)
    except:
        return set(sys.builtin_module_names)


stdlib = get_stdlib()
stdlib.add("app")
stdlib.add("lib")
stdlib.add("config")

dependencies = set()

for root, dirs, files in os.walk("/home/charlie/opt/eye_of_web/src"):
    for file in files:
        if file.endswith(".py"):
            try:
                with open(os.path.join(root, file), "r") as f:
                    tree = ast.parse(f.read())
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for name in node.names:
                                base_module = name.name.split(".")[0]
                                if base_module not in stdlib:
                                    dependencies.add(base_module)
                        elif isinstance(node, ast.ImportFrom):
                            if node.module:
                                base_module = node.module.split(".")[0]
                                if base_module not in stdlib:
                                    dependencies.add(base_module)
            except Exception as e:
                # print(f"Error parsing {file}: {e}")
                pass

print("\nFound External Dependencies:")
for dep in sorted(dependencies):
    print(dep)
