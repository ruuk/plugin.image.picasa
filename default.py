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

def LOG(msg): print msg
def ERROR(msg): LOG(msg)
#xbmc.executebuiltin("Container.SetViewMode(500)")

#protected = private
#private = anyone with link
#public = public

#import xbmc
#print xbmc.getInfoLabel('Skin.CurrentTheme ')
#print xbmc.getSkinDir()
#print 'TES: ' + xbmc.getInfoLabel('Window(Pictures).Property(Viewmode)')

class DeviceOuath2:
	clientID = '905208609020-blro1d2vo7qnjo53ku3ajt6tk40i02ip.apps.googleusercontent.com'
	clientS = '9V-BDq0uD4VN8VAfP0U0wIOp'
	auth1URL = 'https://accounts.google.com/o/oauth2/device/code'
	auth2URL = 'https://accounts.google.com/o/oauth2/token'
	authScope = 'https://picasaweb.google.com/data/'
	grantType = 'http://oauth.net/grant_type/device/1.0'
	baseURL = 'https://picasaweb.google.com'
	
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
		if self.authorized(): LOG('AUTHORIZED')

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
		print url
		#'https://picasaweb.google.com/data/feed/api/{0}/{1}&alt=json'.format(kwargs.get('feed'),kwargs.get('fid'))
		headers = {	'Authorization': 'Bearer ' + self.getToken(),
						'GData-Version':'2'
		}
		resp = self.session.get(url,headers=headers)
		#print resp.headers
		json = resp.json()
		#print json
		return json.get('feed')
		

		
class picasaPhotosSession(AddonHelper):
	def __init__(self,show_image=False):
		AddonHelper.__init__(self,'plugin.image.picasa')
		if show_image: return self.showImage()
		self._api = None
		self.pfilter = None
		self.privacy_levels = ['public','private','protected']
		
		if self.getSetting('use_login',False):
			self.user = 'default'
		else:
			self.user = ''
		
		cache_path = self.dataPath('cache')
		if not os.path.exists(cache_path): os.makedirs(cache_path)
		
		mpp = self.getSettingInt('max_per_page')
		self.max_per_page = [10,20,30,40,50,75,100,200,500,1000][mpp]
		self.isSlideshow = self.getParamString('plugin_slideshow_ss','false') == 'true'
		print 'plugin.image.picasa: isSlideshow: %s' % self.isSlideshow
		
#		update_dir = False
#		cache = True
#	
#		success = self.go(	self.getParamInt('mode',None),
#							self.getParamString('url',None),
#							self.getParamString('name',None),
#							self.getParamString('user',self.user,no_unquote=True))
#		
#		if self.getParamInt('start_index',None): update_dir = True
#		self.endOfDirectory(succeeded=success,updateListing=update_dir,cacheToDisc=cache)
	
	def setApi(self):
		self.auth = None
		if self.getSetting('use_login',False):
			self.auth = DeviceOuath2()
			if not self.auth.authorized():
				self.auth.authorize()
#		import gdata.photos.service
#		headers = {	'Content-Type': 'application/atom+xml',
#						'Authorization': 'Bearer ' + self.auth.getToken(),
#						'GData-Version':'2',
#						'X-GData-Key': 'key=' + 'AIzaSyCt4tydVOveutwJX8CmTbf05y5LLZVwm0A'
#		}
		self._api = self.auth
		#self._api.source = '2ndmind.com-picasaPhotosXBMC'
		#if self.auth: self._api.SetClientLoginToken(self.auth.getToken())
		return self._api
		
	def api(self):
		if self._api: return self._api
		return self.setApi()
		
	def login(self):
		pass
		
	def doCaptcha(self,url,trynum):
		target_file = self.dataPath('cache/captcha_image.jpg')
		fn = self.getFile(url,target_file)
		win = self.xbmcgui().WindowDialog()
		image = self.xbmcgui().ControlImage(0,0,300,105,fn)
		self.endOfDirectory(False,True,True)
		win.addControl(image)
		win.show()
		keyboard = self.xbmc().Keyboard('',self.lang(30304) + str(trynum))
		keyboard.doModal()
		win.close()
		del win
		if keyboard.isConfirmed(): return keyboard.getText()
		return ''
				
	def go(self,mode,url,name,user):
		#print mode,url,name,user
		#for x in range(1,20): self.login()
		#return
		success = False
		terms = ''
		if mode==4 or mode==5:
			terms = self.getParamString('terms')
			if not terms: terms = self.getSearchTerms()
		try:
			success = self.process(mode,url,name,user,terms)
			#print 'NO_LOGIN ' + str(mode)
		except: #TODO more discriminating except clause
			import traceback
			traceback.print_exc()
			if self.user == 'default':
				print 'PHOTOS: LOGIN ' + str(mode)
				if not self.login(): return False #only login if we have to
			success = self.process(mode,url,name,user,terms)
		return success
				
	def process(self,mode,url,name,user,terms):
		if mode==None or url==None or len(url)<1:
			print 'plugin.image.picasa - Version: %s' % self.version() 
			self.CATEGORIES()
		elif mode==1:
			self.ALBUMS(user=url)
		elif mode==2:
			self.TAGS(user=url)
		elif mode==3:
			self.CONTACTS(user=url)
		elif mode==4:
			return self.SEARCH_USER(user=url,terms=terms)
		elif mode==5:
			return self.SEARCH_PICASA(terms=terms)
		elif mode==101:
			self.ALBUM(url,user=user)
		elif mode==102:
			self.TAG(url,user=user)
		elif mode==103:
			self.CONTACT(url,name)
		return True
	
	def showImage(self):
		url = sys.argv[2].split('=',1)[-1]
		url = self.urllib().unquote(url)
		print('plugin.image.picasa - Showing photo with URL: ' + url)
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
		
	def getSearchTerms(self):
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
		self.setViewMode('viewmode_photos')
		
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
			#self.addDir(previous.replace('@REPLACE@',str(per_page)),self.addonPath('resources/images/previous.png'),url=url,mode=mode,start_index=previous_index,**kwargs)
		##---------------------------------------#
		
		mparams = self.getMapParams()
		import time
		for p in photos['entry']:
			if not self.filterAllows(p['gphoto$access']['$t']): continue
			contextMenu = []
			gps = p.get('georss$where')
			if gps:
				gps = ','.join(gps['gml$Point']['gml$pos']['$t'].split())
				contextMenu = [	(self.lang(30405),'XBMC.RunScript(special://home/addons/plugin.image.picasa/maps.py,plugin.image.picasa,%s,%s)' % (gps,mparams)),
								(self.lang(30406) % self.lang(30407),'XBMC.RunScript(special://home/addons/plugin.image.picasa/default.py,viewmode,viewmode_photos)'),
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
			#img_url = self.urllib().quote(img_url)
			#img_url = 'plugin://plugin.image.picasa/?photo_url=' + img_url
			#print img_url,p.media.description.text
			title = p['media$group']['media$description']['$t'] or p['title']['$t'] or p['media$group']['media$title']['$t']
			title = title.replace('\n',' ')
			contextMenu.append(('Download','XBMC.RunScript(special://home/addons/plugin.image.picasa/default.py,download,%s)' % img_url))
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
		
		if end_of_page >= total: return items
		
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
		#self.addDir(next_+' ->',self.addonPath('resources/images/next.png'),url=url,mode=mode,start_index=next_index,**kwargs)
		return plugin.finish(items, update_listing=start != 1)
		#return items
		
	def getCachedThumbnail(self,name,url):
		tn = self.dataPath('cache/' + self.binascii().hexlify(name) + '.jpg')
		if not os.path.exists(tn):
			try:
				return self.getFile(url,tn)
			except:
				return url
		else:
			return tn
				
	def setViewMode(self,setting):
		mode = self.getSetting(setting)
		if mode: self.xbmc().executebuiltin("Container.SetViewMode(%s)" % mode)
	
	@plugin.route('/')
	def CATEGORIES(self):
		items = []
		if self.user:
			items.append({'label':self.lang(30100),'path':plugin.url_for('ALBUMS'),'thumbnail':self.addonPath('resources/images/albums.png')})
			items.append({'label':self.lang(30101),'path':plugin.url_for('TAGS'),'thumbnail':self.addonPath('resources/images/tags.png')})
			items.append({'label':self.lang(30102),'path':plugin.url_for('CONTACTS'),'thumbnail':self.addonPath('resources/images/contacts.png')})
			items.append({'label':self.lang(30103),'path':plugin.url_for('SEARCH_USER'),'thumbnail':self.addonPath('resources/images/search.png')})
		items.append({'label':self.lang(30104),'path':plugin.url_for('SEARCH_PICASA'),'thumbnail':self.addonPath('resources/images/search_picasa.png')})
		return items
		
	@plugin.route('/albums/')
	def ALBUMS(self,user='default'):
		#self.setViewMode('viewmode_albums')
		
		albums = self.api().GetFeed('/data/feed/api/user/%s?kind=album&thumbsize=256c' % (user))
		#tot = len(albums['entry'])
		cm = [(self.lang(30406) % self.lang(30100),'XBMC.RunScript(special://home/addons/plugin.image.picasa/default.py,viewmode,viewmode_albums)')]
		items = []
		for album in albums['entry']:
			if not self.filterAllows(album['gphoto$access']['$t']): continue
			title = '{0} ({1})'.format(album['title']['$t'],album['gphoto$numphotos']['$t'])
			items.append({	'label':title,
							'path':plugin.url_for('ALBUM',ID=album['gphoto$id']['$t']),
							'thumbnail':album['media$group']['media$thumbnail'][0]['url'],
							'context_menu':cm})
		return items
		
	@plugin.route('/tags/')
	def TAGS(self,user='default'):
		self.setViewMode('viewmode_tags')
		
		tags = self.api().GetFeed('/data/feed/api/user/%s?kind=tag' % user)
		tot = int(tags.total_results.text)
		cm = [(self.lang(30406) % self.lang(30101),'XBMC.RunScript(special://home/addons/plugin.image.picasa/default.py,viewmode,viewmode_tags)')]
		for t in tags.entry:
			if not self.addDir(t.title.text,'',tot,contextMenu=cm,url=t.title.text,mode=102,user=user): break
	
	@plugin.route('/contacts/')
	def CONTACTS(self,user='default'):
		self.setViewMode('viewmode_favorites')
		
		contacts = self.api().GetFeed('/data/feed/api/user/%s/contacts?kind=user' % (user))
		tot = int(contacts.total_results.text)
		cm = [(self.lang(30406) % self.lang(30102),'XBMC.RunScript(special://home/addons/plugin.image.picasa/default.py,viewmode,viewmode_favorites)')]
		for c in contacts.entry:
			tn = self.getCachedThumbnail(c.user.text, c.thumbnail.text)
			#tn = c.thumbnail.text
			#tn = tn.replace('s64-c','s256-c').replace('?sz=64','?sz=256')
			if not self.addDir(c.nickname.text,tn,tot,contextMenu=cm,url=c.user.text,mode=103,name=c.nickname.text): break
	
	@plugin.route('/search_user/')
	def SEARCH_USER(self,user='default',terms=''):
		if not terms: return False
		start = self.getParamInt('start_index',1)
		uri = '/data/feed/api/user/%s?kind=photo&q=%s' % (user, terms)
		photos = self.api().GetFeed(uri,limit=self.maxPerPage(),start_index=start)
		self.addPhotos(photos,mode=4,terms=terms)
		return True
		
	@plugin.route('/search/')
	def SEARCH_PICASA(self,terms=''):
		if not terms: return False
		start = self.getParamInt('start_index',1)
		uri = '/data/feed/api/all?q=%s' % (terms.lower())
		photos = self.api().GetFeed(uri,limit=self.maxPerPage(),start_index=start)
		self.addPhotos(photos,mode=5,terms=terms)
		return True
				
	def CONTACT(self,user,name):
		self.setViewMode('viewmode_contact')

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
			
		cm = [(self.lang(30406) % self.lang(30408),'XBMC.RunScript(special://home/addons/plugin.image.picasa/default.py,viewmode,viewmode_contact)')]
		self.addDir(albums,self.addonPath('resources/images/albums.png'),contextMenu=cm,url=user,mode=1)
		self.addDir(tags,self.addonPath('resources/images/tags.png'),contextMenu=cm,url=user,mode=2)
		self.addDir(favs,self.addonPath('resources/images/contacts.png'),contextMenu=cm,url=user,mode=3)
		self.addDir(search,self.addonPath('resources/images/search.png'),contextMenu=cm,url=user,mode=4)
	
	def TAG(self,tag,user='default'):
		start = self.getParamInt('start_index',1)
		uri = '/data/feed/api/user/%s?kind=photo&tag=%s' % (user, tag.lower())
		photos = self.api().GetFeed(uri,limit=self.maxPerPage(),start_index=start)
		self.addPhotos(photos,mode=102,user=user)
	
	@plugin.route('/album/<ID>')
	def ALBUM(self,ID,user='default'):
		start = plugin.request.args.get('start',[1])[0]
		uri = '/data/feed/api/user/%s/albumid/%s?kind=photo' % (user,ID)
		photos = self.api().GetFeed(uri,max_results=self.maxPerPage(),start_index=start)
		return self.addPhotos(photos,'ALBUM',ID)
		
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
	#print "ViewMode: " + view_mode
	AddonHelper('plugin.image.picasa').setSetting(setting,view_mode)
	
def downloadURL():
	url = sys.argv[2]
	import saveurl
	saveurl.SaveURL('plugin.image.picasa',url,'cache')
	
if sys.argv[1] == 'viewmode':
	setViewDefault()
elif sys.argv[1] == 'download':
	downloadURL()
elif len(sys.argv) > 2 and sys.argv[2].startswith('?photo_url'):
	picasaPhotosSession(show_image=True)
else:
	SESSION = picasaPhotosSession()
	plugin.run()
	
