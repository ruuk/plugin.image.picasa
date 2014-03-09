#!/usr/bin/python
import os, sys, time
from addon import AddonHelper

SESSION = None
from xbmcswift2 import Plugin
from xbmcswift2.plugin import log as log__, NotFoundException

class ClassPlugin(Plugin):
	def _dispatch(self, path):
		for rule in self._routes:
			try:
				view_func, items = rule.match(path)
			except NotFoundException:
				continue
			log__.info('Request for "%s" matches rule for function "%s"', path, view_func.__name__)
			listitems = view_func(SESSION,**items)

			if not self._end_of_directory and self.handle >= 0:
				if listitems is None:
					self.finish(succeeded=False)
				else:
					listitems = self.finish(listitems)

			return listitems
		raise NotFoundException, 'No matching view found for %s' % path
								
plugin = ClassPlugin()

__plugin__ =  'picasa'
__author__ = 'ruuk'

def LOG(msg): print 'plugin.image.picasa: %s' % msg

def ERROR(message,hide_tb=False):
	LOG('ERROR: ' + message)
	short = str(sys.exc_info()[1])
	if hide_tb:
		LOG('ERROR Message: ' + short)
	else:
		import traceback #@Reimport
		traceback.print_exc()
	return short


class PicasaWebAPI:
	baseURL = 'https://picasaweb.google.com'
	
	def authorized(self): return False
	
	def GetFeed(self,url=None,*args,**kwargs): raise Exception('Not Implemented')
	
class PicasaWebOauth2API(PicasaWebAPI):
	clientID = '905208609020-blro1d2vo7qnjo53ku3ajt6tk40i02ip.apps.googleusercontent.com'
	clientS = '9V-BDq0uD4VN8VAfP0U0wIOp'
	auth1URL = 'https://accounts.google.com/o/oauth2/device/code'
	auth2URL = 'https://accounts.google.com/o/oauth2/token'
	authScope = 'https://picasaweb.google.com/data/'
	grantType = 'http://oauth.net/grant_type/device/1.0'
	publicAPIKey = 'AIzaSyCt4tydVOveutwJX8CmTbf05y5LLZVwm0A'
	
	def __init__(self):
		self.helper = AddonHelper('plugin.image.picasa')
		self.authPollInterval = 5
		self.authExpires = int(time.time())
		self.deviceCode = ''
		self.verificationURL = 'http://www.google.com/device'
		import requests2 as requests
		self.session = requests.Session()
		self.loadToken()
		
	def loadToken(self):
		self.token = self.helper.getSetting('access_token')
		self.tokenExpires = self.helper.getSetting('token_expiration',0)

	def getToken(self):
		if self.tokenExpires <= int(time.time()):
			return self.updateToken()
		return self.token
		
	def updateToken(self):
		LOG('REFRESHING TOKEN')
		data = {	'client_id':self.clientID,
					'client_secret':self.clientS,
					'refresh_token':self.helper.getSetting('refresh_token'),
					'grant_type':'refresh_token'}
		json = self.session.post(self.auth2URL,data=data).json()
		if 'access_token' in json:
			self.saveData(json)
		else:
			LOG('Failed to update token')
		return self.token
	
	def authorized(self):
		return bool(self.token)
		
	def authorize(self):
		userCode = self.getDeviceUserCode()
		if not userCode: return
		self.showUserCode(userCode)
		import xbmc, xbmcgui
		d = xbmcgui.DialogProgress()
		d.create('Waiting','Waiting for auth...')
		ct=0
		while True:
			d.update(ct,'Waiting for auth...')
			json = self.pollAuthServer()
			if 'access_token' in json: break
			if d.iscanceled(): return
			for x in range(0,self.authPollInterval):
				xbmc.sleep(1000)
				if d.iscanceled(): return
			ct+=1
		return self.saveData(json)
		
	def saveData(self,json):
		self.token = json.get('access_token','')
		refreshToken = json.get('refresh_token')
		self.tokenExpires = json.get('expires_in',3600) + int(time.time())
		self.helper.setSetting('access_token',self.token)
		if refreshToken: self.helper.setSetting('refresh_token',refreshToken)
		self.helper.setSetting('token_expiration',self.tokenExpires)
		return self.token and refreshToken
		
	def pollAuthServer(self):
		json = self.session.post(self.auth2URL,data={	'client_id':self.clientID,
															'client_secret':self.clientS,
															'code':self.deviceCode,
															'grant_type':self.grantType
														}).json()
		if 'error' in json:
			if json['error'] == 'slow_down':
				self.authPollInterval += 1
		return json

	def showUserCode(self,user_code):
		import xbmcgui
		xbmcgui.Dialog().ok('Authorization','Go to: ' + self.verificationURL,'Enter code: ' + user_code,'Click OK when done.')
		
	def getDeviceUserCode(self):
		json = self.session.post(self.auth1URL,data={'client_id':self.clientID,'scope':self.authScope}).json()
		self.authPollInterval = json.get('interval',5)
		self.authExpires = json.get('expires_in',1800) + int(time.time())
		self.deviceCode = json.get('device_code','')
		self.verificationURL = json.get('verification_url',self.verificationURL)
		if 'error' in json:
			LOG('ERROR - getDeviceUserCode(): ' + json.get('error_description',''))
		return json.get('user_code','')
			
	def GetFeed(self,url=None,*args,**kwargs):
		url = self.baseURL + url + '&alt=json'
		for k,v in kwargs.items():
			url += '&{0}={1}'.format(k.replace('_','-'),v)
		headers = {	'Authorization': 'Bearer ' + self.getToken(),
						'GData-Version':'2'
		}
		resp = self.session.get(url,headers=headers)
		try:
			json = resp.json()
		except:
			print resp.text
			raise
		return json.get('feed')
		
class PicasaWebPublicAPI(PicasaWebAPI):
	publicAPIKey = 'AIzaSyCt4tydVOveutwJX8CmTbf05y5LLZVwm0A'
	
	def __init__(self):
		import requests2 as requests
		self.session = requests.Session()
		
	def GetFeed(self,url=None,*args,**kwargs):
		url = self.baseURL + url + '&alt=json'
		for k,v in kwargs.items():
			url += '&{0}={1}'.format(k.replace('_','-'),v)
		headers = {	'X-GData-Key': 'key=' + self.publicAPIKey,
						'GData-Version':'2'
		}
		resp = self.session.get(url,headers=headers)
		try:
			json = resp.json()
		except:
			print resp.text
			raise
		return json.get('feed')
		
class picasaPhotosSession(AddonHelper):
	def __init__(self,show_image=False):
		AddonHelper.__init__(self,'plugin.image.picasa')
		if show_image: return self.showImage()
		self._api = None
		self.pfilter = None
		self.privacy_levels = ['public','private','protected']
		
		if self.getSetting('use_login',False):
			self._user = 'default'
		else:
			self._user = self.getSetting('username')
		
		cache_path = self.dataPath('cache')
		if not os.path.exists(cache_path): os.makedirs(cache_path)
		
		mpp = self.getSettingInt('max_per_page')
		self.max_per_page = [10,20,30,40,50,75,100,200,500,1000][mpp]
		self.isSlideshow = self.getParamString('plugin_slideshow_ss','false') == 'true'
		LOG('isSlideshow: %s' % self.isSlideshow)
	
	def setApi(self):
		self._api = None
		if self.getSetting('use_login',False):
			self._api = PicasaWebOauth2API()
			if not self._api.authorized():
				self._api.authorize()
		else:
			self._api = PicasaWebPublicAPI()
		return self._api
		
	def api(self):
		if self._api: return self._api
		return self.setApi()
	
	def showImage(self):
		url = sys.argv[2].split('=',1)[-1]
		url = self.urllib().unquote(url)
		LOG('Showing photo with URL: ' + url)
		image_path = os.path.join(self.dataPath('cache'),'image.jpg')
		open(image_path,'w').write(self.urllib2().urlopen(url).read())
		listitem = self.xbmcgui().ListItem(label='PicasaWeb Photo', path=image_path)
		listitem.setInfo(type='pictures',infoLabels={"Title": 'PicasaWeb Photo'})
		self.xbmcplugin().setResolvedUrl(handle=int(sys.argv[1]), succeeded=True, listitem=listitem)
		
	def filterAllows(self,privacy):
		if privacy == 'only_you': privacy = 'protected'
		if not self.pfilter: self.pfilter = self.getSettingInt('privacy_filter')
		if not privacy in self.privacy_levels: return False
		level = self.privacy_levels.index(privacy)
		if level <= self.pfilter: return True
		return False
		
	def getSearchTerms(self,terms=''):
		terms = terms or plugin.request.args.get('terms',[''])[0]
		if terms: return terms
		keyboard = self.xbmc().Keyboard('',self.lang(30404))
		keyboard.doModal()
		if keyboard.isConfirmed(): return keyboard.getText()
		return ''
			
	def getMapParams(self):
		mtype = ['hybrid','satellite','terrain','roadmap'][self.getSettingInt('default_map_type')]
		msource = ['google','yahoo','osm'][self.getSettingInt('default_map_source')]
		mzoom = self.getSetting('map_zoom')
		return "type=%s&source=%s&zoom=%s" % (mtype,msource,mzoom)
		
	def addPhotos(self,photos,source='',ID=''):		
		total = photos['openSearch$totalResults']['$t']
		start = photos['openSearch$startIndex']['$t']
		per_page = photos['openSearch$itemsPerPage']['$t']
		items = []
		## Previous Page ------------------------#
		if start > 1:
			previous = '<- '+ self.lang(30401)
			previous_index = start - per_page
			items.append({	'label':previous.replace('@REPLACE@',str(per_page)),
							'path':plugin.url_for(source,ID=ID,start=previous_index),
							'thumbnail':self.addonPath('resources/images/previous.png'),
			})
		##---------------------------------------#
		
		mparams = self.getMapParams()
		import time
		for p in photos.get('entry',[]):
			if not self.filterAllows(p['gphoto$access']['$t']): continue
			contextMenu = []
			gps = p.get('georss$where')
			if gps:
				gps = ','.join(gps['gml$Point']['gml$pos']['$t'].split())
				contextMenu = [	(self.lang(30405),'XBMC.RunScript(special://home/addons/plugin.image.picasa/maps.py,plugin.image.picasa,%s,%s)' % (gps,mparams)),
								(self.lang(30406) % self.lang(30407),'XBMC.RunScript(plugin.image.picasa,viewmode,viewmode_photos)'),
								]
			content = p['media$group']['media$content']
			mtype = ''
			video = ''
			img_url = ''
			for c in content:
				if c['type'].startswith('video'):
					mtype = 'video'
					video = c['url']
				elif c['type'].startswith('image'):
					mtype = 'pictures'
					img_url = c['url']
			img_url = p['media$group']['media$content'][-1]['url']
			first,second = img_url.rsplit('/',1)
			img_url = '/'.join([first,'s0',second]) + '&t=' + str(time.time()) #without this, photos larger than 2048w XBMC says: "Texture manager unable to load file:" - Go Figure
			title = p['media$group']['media$description']['$t'] or p['title']['$t'] or p['media$group']['media$title']['$t']
			title = title.replace('\n',' ')
			contextMenu.append(('Download','XBMC.RunScript(plugin.image.picasa,download,%s)' % self.urllib().quote(img_url)))
			if p['media$group']['media$thumbnail'] and len(p['media$group']['media$thumbnail']) > 2:
				thumb = p['media$group']['media$thumbnail'][2]['url']
			else:
				thumb = p['media$group']['media$thumbnail'][0]['url']
			items.append({	'label':title,
							'path':mtype == 'video' and video or img_url,
							'thumbnail':thumb,
							'context_menu':contextMenu,
							'info':{'type':mtype},
							'is_playable':True
			})
			
		## Next     Page ------------------------#
		end_of_page =  (start + per_page) - 1
		
		if end_of_page >= total: return plugin.finish(items, update_listing=not self.initial(), view_mode=self.getViewMode('viewmode_photos'))
		
		next_ = '('+str(end_of_page)+'/'+str(total)+') '
		
		maybe_left = total - end_of_page
		if maybe_left <= per_page:
			next_ += self.lang(30403).replace('@REPLACE@',str(maybe_left))
		else:
			next_ += self.lang(30402).replace('@REPLACE@',str(per_page))
		
		next_index = start + per_page
		items.append({	'label':next_+' ->',
						'path':plugin.url_for(source,ID=ID,start=next_index),
						'thumbnail':self.addonPath('resources/images/next.png'),
		})
		return plugin.finish(items, update_listing=not self.initial(), view_mode=self.getViewMode('viewmode_photos'))
		
	def getCachedThumbnail(self,name,url):
		tn = self.dataPath('cache/' + self.binascii().hexlify(name) + '.jpg')
		if not os.path.exists(tn):
			try:
				return self.getFile(url,tn)
			except:
				return url
		else:
			return tn
		
	@plugin.route('/')
	def CATEGORIES(self):
		LOG(('Version: %s' % self.version()) + (self.api().authorized() and ' AUTHORIZED' or ''))
		items = []
		if self.user():
			items.append({'label':self.lang(30100),'path':plugin.url_for('ALBUMS'),'thumbnail':self.addonPath('resources/images/albums.png')})
			items.append({'label':self.lang(30101),'path':plugin.url_for('TAGS'),'thumbnail':self.addonPath('resources/images/tags.png')})
			items.append({'label':self.lang(30102),'path':plugin.url_for('CONTACTS'),'thumbnail':self.addonPath('resources/images/contacts.png')})
			items.append({'label':self.lang(30103),'path':plugin.url_for('SEARCH_USER'),'thumbnail':self.addonPath('resources/images/search.png')})
		items.append({'label':self.lang(30104),'path':plugin.url_for('SEARCH_PICASA'),'thumbnail':self.addonPath('resources/images/search_picasa.png')})
		return items
		
	@plugin.route('/albums/')
	def ALBUMS(self):
		user = self.user()
		
		albums = self.api().GetFeed('/data/feed/api/user/%s?kind=album&thumbsize=256c' % (user))
		#tot = len(albums['entry'])
		cm = [(self.lang(30406) % self.lang(30100),'XBMC.RunScript(plugin.image.picasa,viewmode,viewmode_albums)')]
		items = []
		for album in albums.get('entry',[]):
			if not self.filterAllows(album['gphoto$access']['$t']): continue
			title = '{0} ({1})'.format(album['title']['$t'],album['gphoto$numphotos']['$t'])
			items.append({	'label':title,
							'path':plugin.url_for('ALBUM',ID=album['gphoto$id']['$t'],user=user),
							'thumbnail':album['media$group']['media$thumbnail'][0]['url'],
							'context_menu':cm})
		return plugin.finish(items,view_mode=self.getViewMode('viewmode_albums'))
		
	@plugin.route('/tags/')
	def TAGS(self):
		user = self.user()
		
		tags = self.api().GetFeed('/data/feed/api/user/%s?kind=tag' % user)
		#tot = int(tags.total_results.text)
		cm = [(self.lang(30406) % self.lang(30101),'XBMC.RunScript(plugin.image.picasa,viewmode,viewmode_tags)')]
		items = []
		for t in tags.get('entry',[]):
			items.append({	'label':t['title']['$t'],
							'path':plugin.url_for('TAG',ID=t['title']['$t'],user=user),
							'thumbnail':self.addonPath('resources/images/tags.png'),
							'context_menu':cm})
		return plugin.finish(items, view_mode=self.getViewMode('viewmode_tags'))
	
	@plugin.route('/contacts/')
	def CONTACTS(self):		
		contacts = self.api().GetFeed('/data/feed/api/user/%s/contacts?kind=user' % (self.user()))
		#tot = int(contacts.total_results.text)
		cm = [(self.lang(30406) % self.lang(30102),'XBMC.RunScript(plugin.image.picasa,viewmode,viewmode_favorites)')]
		items = []
		for c in contacts.get('entry',[]):
			tn = self.getCachedThumbnail(c['gphoto$user']['$t'], c['gphoto$thumbnail']['$t'])
			#tn = c['thumbnail']['$t']
			#tn = tn.replace('s64-c','s256-c').replace('?sz=64','?sz=256')
			items.append({	'label':c['gphoto$nickname']['$t'],
							'path':plugin.url_for('CONTACT',user=c['gphoto$user']['$t'],name=c['gphoto$nickname']['$t']),
							'thumbnail':tn,
							'context_menu':cm})
		return plugin.finish(items, view_mode=self.getViewMode('viewmode_favorites'))
		
	@plugin.route('/search_user/')
	@plugin.route('/search_user/<ID>',name='SEARCH_USER_PAGE')
	def SEARCH_USER(self,ID=''):
		terms = self.getSearchTerms(ID)
		uri = '/data/feed/api/user/%s?kind=photo&q=%s' % (self.user(), terms)
		photos = self.api().GetFeed(uri,max_results=self.maxPerPage(),start_index=self.start())
		return self.addPhotos(photos,'SEARCH_USER_PAGE',terms)
		
	@plugin.route('/search/')
	@plugin.route('/search/<ID>',name='SEARCH_PICASA_PAGE')
	def SEARCH_PICASA(self,ID=''):
		terms = self.getSearchTerms(ID)
		uri = '/data/feed/api/all?q=%s' % (terms.lower())
		photos = self.api().GetFeed(uri,max_results=self.maxPerPage(),start_index=self.start())
		return self.addPhotos(photos,'SEARCH_PICASA_PAGE',terms)
	
	@plugin.route('/contact/<user>')
	def CONTACT(self,user):
		name = plugin.request.args.get('name',[''])[0]

		#fix for names ending in 
		if name[-1].lower() == 's':
			albums = self.lang(30200).replace("@REPLACE@'s",name + "'").replace('@REPLACE@',name)
			tags = self.lang(30201).replace("@REPLACE@'s",name + "'").replace('@REPLACE@',name)
			favs = self.lang(30202).replace("@REPLACE@'s",name + "'").replace('@REPLACE@',name)
			search = self.lang(30203).replace("@REPLACE@'s",name + "'").replace('@REPLACE@',name)
		else:
			albums = self.lang(30200).replace('@REPLACE@',name)
			tags = self.lang(30201).replace('@REPLACE@',name)
			favs = self.lang(30202).replace('@REPLACE@',name)
			search = self.lang(30203).replace('@REPLACE@',name)
			
		cm = [(self.lang(30406) % self.lang(30408),'XBMC.RunScript(plugin.image.picasa,viewmode,viewmode_contact)')]
		items = []
		items.append({	'label':albums,
						'path':plugin.url_for('ALBUMS',user=user),
						'thumbnail':self.addonPath('resources/images/albums.png'),
						'context_menu':cm
		})
		items.append({	'label':tags,
						'path':plugin.url_for('TAGS',user=user),
						'thumbnail':self.addonPath('resources/images/tags.png'),
						'context_menu':cm
		})
		items.append({	'label':favs,
						'path':plugin.url_for('CONTACTS',user=user),
						'thumbnail':self.addonPath('resources/images/contacts.png'),
						'context_menu':cm
		})
		items.append({	'label':search,
						'path':plugin.url_for('SEARCH_USER',user=user),
						'thumbnail':self.addonPath('resources/images/searcg.png'),
						'context_menu':cm
		})
		return plugin.finish(items, view_mode=self.getViewMode('viewmode_contact'))
	
	@plugin.route('/tag/<ID>')
	def TAG(self,ID):
		uri = '/data/feed/api/user/%s?kind=photo&tag=%s' % (self.user(), ID.lower())
		photos = self.api().GetFeed(uri,max_results=self.maxPerPage(),start_index=self.start())
		return self.addPhotos(photos,'TAG',ID)
	
	@plugin.route('/album/<ID>')
	def ALBUM(self,ID):
		uri = '/data/feed/api/user/%s/albumid/%s?kind=photo' % (self.user(),ID)
		photos = self.api().GetFeed(uri,max_results=self.maxPerPage(),start_index=self.start())
		return self.addPhotos(photos,'ALBUM',ID)
		
	def user(self):
		return plugin.request.args.get('user',[self._user])[0]
		
	def start(self):
		return plugin.request.args.get('start',[1])[0]
		
	def initial(self):
		return not plugin.request.args.get('start')
	
	def getViewMode(self,setting):
		return self.getSetting(setting) or None
		
	def maxPerPage(self):
		if self.isSlideshow: return 1000
		return self.max_per_page
			
def setViewDefault():
	import xbmc #@UnresolvedImport
	setting = sys.argv[2]
	view_mode = ""
	for ID in range( 50, 59 ) + range(500,600):
		try:
			if xbmc.getCondVisibility( "Control.IsVisible(%i)" % ID ):
				view_mode = repr( ID )
				break
		except:
			pass
	if not view_mode: return
	AddonHelper('plugin.image.picasa').setSetting(setting,view_mode)
	
def downloadURL():
	import urllib
	url = urllib.unquote(sys.argv[2])
	import saveurl
	saveurl.SaveURL('plugin.image.picasa',url,'cache')
	
if sys.argv[1] == 'viewmode':
	setViewDefault()
elif sys.argv[1] == 'download':
	downloadURL()
elif len(sys.argv) > 2 and sys.argv[2].startswith('?photo_url'):
	picasaPhotosSession(show_image=True)
else:
	try:
		SESSION = picasaPhotosSession()
		plugin.run()
	except:
		ERROR('FAIL')
	
