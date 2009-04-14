
import os, re, StringIO
import ConfigParser, pkgutil

import sonata.plugins

def find_plugin_dirs():
	return [os.path.expanduser('~/.sonata/plugins'),
		'/usr/local/lib/sonata/plugins']

# add dirs from sys.path:
sonata.plugins.__path__ = pkgutil.extend_path(sonata.plugins.__path__, 
					      sonata.plugins.__name__)
# add dirs specific to sonata:
sonata.plugins.__path__ = find_plugin_dirs() + sonata.plugins.__path__


class Plugin(object):
	def __init__(self, path, name, info, load):
		self.path = path
		self.name = name
		self._info = info
		self._load = load
		# obligatory plugin info:
		format_value = info.get('plugin', 'plugin_format')
		self.plugin_format = tuple(map(int, format_value.split(',')))
		self.longname = info.get('plugin', 'name')
		versionvalue = info.get('plugin', 'version')
		self.version = tuple(map(int, versionvalue.split(',')))
		self.version_string = '.'.join(map(str, self.version))
		self._capabilities =  dict(info.items('capabilities'))
		# optional plugin info:
		try:
			self.description = info.get('plugin', 'description')
		except ConfigParser.NoOptionError:
			self.description = ""
		try:
			self.author = info.get('plugin', 'author')
		except:
			self.author = ""
		try:
			self.author_email = info.get('plugin', 'author_email')
		except:
			self.author_email = ""
		try:
			self.iconurl = info.get('plugin', 'icon')
		except ConfigParser.NoOptionError:
			self.iconurl = None
		try:
			self.url = info.get('plugin', 'url')
		except:
			self.url = ""
		# state:
		self._module = None # lazy loading
		self._enabled = False

	def get_enabled(self):
		return self._enabled

	def get_features(self, capability):
		if not self._enabled or not capability in self._capabilities:
			return []

		module = self._get_module()
		if not module:
			return []

		features = self._capabilities[capability]
		try:
			return [getattr(module, f)
				for f in features.split(', ')]
		except KeyboardInterrupt:
			raise
		except "Exception":
			print ("Failed to access features in plugin %s." % 
			       self.name)
			return []

	def _get_module(self):
		if not self._module:
			try:
				self._module = self._load()
			except Exception:
				print "Failed to load plugin %s." % self.name
				return None
		return self._module

	def force_loaded(self):
		return bool(self._get_module())
		
class PluginSystem(object):
	def __init__(self):
		self.plugin_infos = []
		self.loaded_plugins = {}
		self.notifys = []

	def get_info(self):
		return self.plugin_infos

	def get(self, capability):
		return [(plugin, feature)
			for plugin in self.plugin_infos
			for feature in plugin.get_features(capability)]

	def notify_of(self, capability, enable_cb, disable_cb):
		self.notifys.append((capability, enable_cb, disable_cb))
		for plugin, feature in self.get(capability):
			enable_cb(plugin, feature)

	def set_enabled(self, plugin, state):
		if plugin._enabled != state:
			# make notify callbacks for each feature of the plugin:
			plugin._enabled = True # XXX for plugin.get_features
			
			# process the notifys in the order they were registered:
			for capability, enable, disable in self.notifys:
				callback = enable if state else disable
				for feature in plugin.get_features(capability):
					callback(plugin, feature)
			plugin._enabled = state

	def find_plugins(self):
		for path in sonata.plugins.__path__:
			if not os.path.isdir(path):
				continue
			for entry in os.listdir(path):
				if entry.startswith('_'):
					continue # __init__.py etc.
				if entry.endswith('.py'):
					try:
						self.load_info(path, entry[:-3])
					except Exception:
						print "Failed to load info:", 
						print os.path.join(path, entry)

	def load_info(self, path, name):
		f = open(os.path.join(path, name+".py"), "rt")
		text = f.read()
		f.close()

		pat = r'^### BEGIN PLUGIN INFO.*((\n#.*)*)\n### END PLUGIN INFO'
		infotext = re.search(pat, text, re.MULTILINE).group(1)
		uncommented = '\n'.join(line[1:].strip() 
					for line in infotext.split('\n'))
		info = ConfigParser.SafeConfigParser()
		info.readfp(StringIO.StringIO(uncommented))

		# XXX add only newest version of each name
		plugin = Plugin(path, name, info, 
				lambda:self.import_plugin(name))

		self.plugin_infos.append(plugin)

		if not info.options('capabilities'):
			print "Warning: No capabilities in plugin %s." % name

	def load_plugin(self, _path, name):
		# XXX load from a .py file - no .pyc etc.
		plugin = self.import_plugin(name)
		self.loaded_plugins[name] = plugin
		return plugin

	def import_plugin(self, name):
		__import__('sonata.plugins', {}, {}, [name], 0)
		plugin = getattr(sonata.plugins, name)
		return plugin

pluginsystem = PluginSystem()
