import os
import json
import sys
import argparse
from .utils.pypi_api import get_avaliable_versions
from .utils.version import wanted_version, sort_versions
from .utils import sneak_config, package_json, python_modules
import pip
from .node import Node
from .utils.tabulate import tabulate

class CommandOutdated():
	name = "outdated"
	@staticmethod
	def decorate_subparser(subparser):
		pass
	@classmethod
	def run(cls, args):
		cls._run()
	@classmethod
	def _run(cls):
		packages = python_modules.get_packages(os.path.join(os.getcwd(), "python_modules"))
		dependencies = package_json.get_dependencies()
		if len(dependencies) == 0:
			return
		package_metadatas = []
		for dependency, version in dependencies.items():
			package_metadata = python_modules.get_package_metadata(packages, dependency)
			package_metadata["version_markup"] = version
			versions_metadata = get_avaliable_versions(dependency)
			# package_metadata["avaliable_versions_metadata"] = versions_metadata
			package_metadata["avaliable_versions"] = list(map(lambda version: version["version"], versions_metadata))
			package_metadata["latest"] = sort_versions(package_metadata["avaliable_versions"])[-1:][0]
			package_metadata["wanted_version"] = wanted_version(version, package_metadata["avaliable_versions"])
			if not "version" in package_metadata or (
				package_metadata["version"] != package_metadata["latest"] or
				package_metadata["version"] != package_metadata["wanted_version"]):
				package_metadatas.append(package_metadata)
		cls.display_outdated(package_metadatas)
	@staticmethod
	def display_outdated(metadatas):
		class Colors:
			PURPLE = '\033[95m'
			OKBLUE = '\033[94m'
			OKGREEN = '\033[92m'
			WARNING = '\033[93m'
			FAIL = '\033[91m'
			UNDERLINE = '\033[4m'
			ENDC = '\033[0m'

		headings = ["Package", "current", "wanted", "latest"]
		headings = list(map(lambda heading: Colors.UNDERLINE+heading+Colors.ENDC, headings))
		table = []
		metadatas = sorted(metadatas, key=lambda metadata: metadata["name"])
		for metadata in metadatas:
			if "version" in metadata:
				current_version = metadata["version"]
			else:
				current_version = "n/a"
			table.append([
				Colors.OKGREEN+metadata["name"]+Colors.ENDC,
				current_version,
				Colors.OKGREEN+metadata["wanted_version"]+Colors.ENDC,
				Colors.PURPLE+metadata["latest"]+Colors.ENDC
			])
		print(tabulate(table, headings, tablefmt="plain"))

class CommandRemove():
	name = "remove"
	@staticmethod
	def decorate_subparser(subparser):
		subparser.add_argument('program', type=str, nargs='?')
		subparser.add_argument("-s", "--save", action='store_true')
	@classmethod
	def run(cls, args):
		cls._run(args.program, args.save)
	@staticmethod
	def _run(package, save):
		def package_json_if_save(save):
			if save:
				dependencies = package_json.get_dependencies()
				dependencies.pop(package, None)
				package_json.write_dependencies(dependencies)
		import shutil
		metadata = python_modules.get_package(os.path.join(os.getcwd(), "python_modules"), package)
		if not metadata:
			print("package "+package+" is not installed")
			package_json_if_save(save)
			return
		pending_removals = []
		pending_removals += metadata["top_level"]
		pending_removals.append(metadata["dist_info"])
		for pending_removal in pending_removals:
			try:
				shutil.rmtree(os.path.join("python_modules", pending_removal))
			except:
				try:
					os.remove(os.path.join("python_modules", pending_removal+".py"))
				except:
					pass
		package_json_if_save(save)
	@classmethod
	def execute(cls, package):
		# Code interface
		cls._run(package, False)

class CommandInstall():
	name = "install"
	@staticmethod
	def decorate_subparser(subparser):
		subparser.add_argument('program', type=str, nargs='?')
		subparser.add_argument("-s", "--save", action='store_true')
	@classmethod
	def run(cls, args):
		cls._run(args.program, args.save)
	@classmethod
	def _run(cls, package, save):
		def package_json_if_save(save, version_markup):
			if save:
				dependencies = package_json.get_dependencies()
				dependencies[package] = version_markup
				package_json.write_dependencies(dependencies)
		if not package:
			installed_package_metadatas = python_modules.get_packages(os.path.join(os.getcwd(), "python_modules"))
			installed_package_names = list(map(lambda md: md["name"], installed_package_metadatas))
			dependencies = package_json.get_dependencies()
			install_queue = []
			for dependency in dependencies:
				if not dependency in installed_package_names:
					install_queue.append({
						"name": dependency,
						"version": dependencies[dependency]
					})
			for item in install_queue:
				versions = list(map(lambda md: md["version"], get_avaliable_versions(item["name"])))
				wanted = wanted_version(item["version"], versions)
				cls.perform_install(item["name"], wanted)
		else:
			latest_version = cls.install_latest(package)
			if not latest_version:
				return
			package_json_if_save(save, "^"+latest_version)
	@staticmethod
	def perform_install(package, version=None, upgrade=False):
		sneak_config.sneak_config_setup()
		if version:
			install_item = package+"=="+version
		else:
			install_item = package
		print(install_item)
		command = ['install', install_item, "--target="+os.path.join(os.getcwd(), "python_modules")]
		if upgrade:
			command.append("--upgrade")
		pip.main(command)
		sneak_config.sneak_config_remove()
	@classmethod
	def install_latest(cls, package):
		avaliable_versions = get_avaliable_versions(package)
		if avaliable_versions == None:
			print("Unable to find package "+package)
			return None
		if len(avaliable_versions) == 0:
			print("Unable to find releases for package "+package)
			return None
		versions = list(map(lambda version: version["version"], avaliable_versions))
		latest_version = sort_versions(versions)[-1:][0]
		cls.perform_install(package, latest_version, True)
		return latest_version

class CommandList():
	name = "list"
	@staticmethod
	def decorate_subparser(subparser):
		pass
	@classmethod
	def run(cls, args):
		cls._run()
	@staticmethod
	def _run():
		print(os.getcwd())
		installed_package_metadatas = python_modules.get_packages(os.path.join(os.getcwd(), "python_modules"))
		dependencies = package_json.get_dependencies()
		tree = Node()
		unwanted = []
		for metadata in installed_package_metadatas:
			if metadata["name"] in dependencies:
				tree.children.append(Node(metadata))
				metadata["touched"] = True
		for node in tree.children:
			node.build_tree_level(installed_package_metadatas)
		for metadata in installed_package_metadatas:
			if metadata.get("touched", False) == False:
				unwanted.append(metadata)
		print(tree)
		if len(unwanted) > 0:
			print("Unwanted:")
			print(list(map(lambda a: a["name"], unwanted)))

class CommandPrune():
	name = "prune"
	@staticmethod
	def decorate_subparser(subparser):
		pass
	@classmethod
	def run(cls, args):
		cls._run()
	@staticmethod
	def _run():
		installed_package_metadatas = python_modules.get_packages(os.path.join(os.getcwd(), "python_modules"))
		dependencies = package_json.get_dependencies()
		tree = Node()
		unwanted = []
		for metadata in installed_package_metadatas:
			if metadata["name"] in dependencies:
				tree.children.append(Node(metadata))
				metadata["touched"] = True
		for node in tree.children:
			node.build_tree_level(installed_package_metadatas)
		for metadata in installed_package_metadatas:
			if metadata.get("touched", False) == False:
				unwanted.append(metadata)
		for metadata in unwanted:
			CommandRemove.execute(metadata["name"])

class CommandInit():
	name = "init"
	@staticmethod
	def decorate_subparser(subparser):
		pass
	@classmethod
	def run(cls, args):
		cls._run()
	@staticmethod
	def _run():
		package_file_path = os.path.join(os.getcwd(), 'package.json')
		if os.path.isfile(package_file_path):
			print("package.json already exists")
			return
		with open(package_file_path, 'w') as outfile:
			file_content = {
				"pythonDevDependencies": {},
				"pythonDependencies": {}
			}
			json.dump(file_content, outfile, indent=2)

def main():
	subcommands = [
		CommandOutdated,
		CommandInstall,
		CommandRemove,
		CommandList,
		CommandPrune,
		CommandInit
	]

	parser = argparse.ArgumentParser(description=("Python Package Manager"))
	subparsers = parser.add_subparsers(dest='subcommand')

	for subcommand in subcommands:
		subparser = subparsers.add_parser(subcommand.name)
		subcommand.decorate_subparser(subparser)

	args = parser.parse_args()

	for subcommand in subcommands:
		if args.subcommand == subcommand.name:
			subcommand.run(args)

if __name__ == '__main__':
	sys.exit(main())

