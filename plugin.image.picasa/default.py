#!/usr/bin/python
import urllib, os
from addon import AddonHelper

__plugin__ =  'picasa'
__author__ = 'ruuk'
__url__ = 'http://code.google.com/p/picasaphotos-xbmc/'
__date__ = '10-19-2010'
__version__ = '0.8.1'
		
class picasaPhotosSession(AddonHelper):
	def __init__(self):
		AddonHelper.__init__(self,'plugin.image.picasa')
		self._api = None
		
		cache_path = self.dataPath('cache')
		if not os.path.exists(cache_path): os.makedirs(cache_path)
		
		mpp = self.getSettingInt('max_per_page')
		self.max_per_page = [10,20,30,40,50,75,100,200,500,1000][mpp]
		
		update_dir = False
		cache = True
	
		success = self.go(	self.getParamInt('mode',None),
							self.getParamString('url',None),
							self.getParamString('name',None),
							self.getParamString('user','default',no_unquote=True))
		
		if self.getParamInt('start_index',None): update_dir = True
		self.endOfDirectory(succeeded=success,updateListing=update_dir,cacheToDisc=cache)
	
	def setApi(self):
		import gdata.photos.service
		self._api = gdata.photos.service.PhotosService()
		self._api.email = self.getSetting('login_email')
		self._api.password = self.getSetting('login_pass')
		self._api.source = '2ndmind.com-picasaPhotosXBMC'
		token_path = self.dataPath('token')
		if os.path.exists(token_path):
			f = open(token_path,'r')
			token = f.read()
			f.close()
			self._api.SetClientLoginToken(token)
		return self._api
		
	def api(self):
		if self._api: return self._api
		return self.setApi()
		
	def login(self):
		from gdata.service import CaptchaRequired,BadAuthentication
		login = True
		fail = ''
		try:
			self.api().ProgrammaticLogin()
		except CaptchaRequired,e:
			login = False
			fail = 'captcha'
		except BadAuthentication,e:
				fail = 'badauth'
			
		ct=0
		while fail == 'captcha' and not login:
			try:
				ctoken = self.api()._GetCaptchaToken()
				curl = self.api()._GetCaptchaURL()
				#show image, get response
				response = self.doCaptcha(curl,ct+1)
				if not response: break
				print response,ctoken
				self.api().ProgrammaticLogin(ctoken,response)
				break
			except CaptchaRequired,e:
				fail = 'captcha'
				print 'CAPTCHA FAIL'
			except BadAuthentication,e:
				fail = 'badauth'
				print 'BAD AUTHENTICATION'
			if ct > 2: break
			ct+=1
				
		token = self.api().GetClientLoginToken()
		if not token:
			if fail == 'captcha':
				self.xbmcgui().Dialog().ok(self.lang(30300),self.lang(30300),self.lang(30301),'http://google.com/accounts/DisplayUnlockCaptcha')
			elif fail == 'badauth':
				self.xbmcgui().Dialog().ok(self.lang(30302),self.lang(30302),self.lang(30303))
			return False
			
		token_path = self.dataPath('token')
		f = open(token_path,'w')
		f.write(token)
		f.close()
		return True
		
	def doCaptcha(self,url,trynum):
		fn = self.getFile(url)
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
		print mode,url,name,user
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
			print 'FACEBOOKPHOTOS: LOGIN ' + str(mode)
			if not self.login(): return False #only login if we have to
			success = self.process(mode,url,name,user,terms)
		return success
				
	def process(self,mode,url,name,user,terms):
		if mode==None or url==None or len(url)<1:
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
		
	def addPhotos(self,photos,mode=None,**kwargs):
		total = int(photos.total_results.text)
		start = int(photos.start_index.text)
		per_page = int(photos.items_per_page.text)
		url = self.getParamString('url','default')
		
		## Previous Page ------------------------#
		if start > 1:
			previous = '<- '+ self.lang(30401)
			previous_index = start - per_page
			self.addDir(previous.replace('@REPLACE@',str(per_page)),self.addonPath('resources/images/previous.png'),url=url,mode=mode,start_index=previous_index,**kwargs)
		##---------------------------------------#
		
		mparams = self.getMapParams()
		
		for p in photos.entry:
			contextMenu = None
			lat_lon = p.geo.Point.pos.text
			if lat_lon:
				lat_lon = ','.join(lat_lon.split())
				contextMenu = [(self.lang(30405),'XBMC.RunScript(special://home/addons/plugin.image.picasa/maps.py,plugin.image.picasa,%s,%s)' % (lat_lon,mparams))]
			if not self.addLink(p.title.text,p.content.src,p.media.thumbnail[2].url,total=total,contextMenu=contextMenu): break
			
		## Next     Page ------------------------#
		total = int(photos.total_results.text)
		end_of_page =  (start + per_page) - 1
		
		if end_of_page >= total: return
		
		next = '('+str(end_of_page)+'/'+str(total)+') '
		
		maybe_left = total - end_of_page
		if maybe_left <= per_page:
			next += self.lang(30403).replace('@REPLACE@',str(maybe_left))
		else:
			next += self.lang(30402).replace('@REPLACE@',str(per_page))
		
		next_index = start + per_page
		self.addDir(next+' ->',self.addonPath('resources/images/next.png'),url=url,mode=mode,start_index=next_index,**kwargs)
		##---------------------------------------#
	
	def CATEGORIES(self):
		self.addDir(self.lang(30100),url='default',mode=1,_thumbnail=self.addonPath('resources/images/albums.png'))
		self.addDir(self.lang(30101),url='default',mode=2,_thumbnail=self.addonPath('resources/images/tags.png'))
		self.addDir(self.lang(30102),url='default',mode=3,_thumbnail=self.addonPath('resources/images/contacts.png'))
		self.addDir(self.lang(30103),url='default',mode=4,_thumbnail=self.addonPath('resources/images/search.png'))
		self.addDir(self.lang(30104),url='default',mode=5,_thumbnail=self.addonPath('resources/images/search_picasa.png'))
		
	def ALBUMS(self,user='default'):
		albums = self.api().GetFeed('/data/feed/api/user/%s?kind=album&thumbsize=256c' % (user))
		#albums = self.api().GetUserFeed(user=user)
		tot = int(albums.total_results.text)
		for album in albums.entry:
			title = album.title.text + ' (' + album.numphotos.text + ')'
			if not self.addDir(title,album.media.thumbnail[0].url,tot,url=album.gphoto_id.text,mode=101,user=user): break
			
	def TAGS(self,user='default'):
		tags = self.api().GetFeed('/data/feed/api/user/%s?kind=tag' % user)
		tot = int(tags.total_results.text)
		for t in tags.entry:
			if not self.addDir(t.title.text,'',tot,url=t.title.text,mode=102,user=user): break
			
	def CONTACTS(self,user='default'):
		contacts = self.api().GetFeed('/data/feed/api/user/%s/contacts?kind=user' % (user))
		tot = int(contacts.total_results.text)
		for c in contacts.entry:
			tn = self.dataPath('cache/' + c.user.text + '.jpg')
			if not os.path.exists(tn):
				tn = self.getFile(c.thumbnail.text,tn)
			#tn = c.thumbnail.text
			#tn = tn.replace('s64-c','s256-c').replace('?sz=64','?sz=256')
			if not self.addDir(c.nickname.text,tn,tot,url=c.user.text,mode=103,name=c.nickname.text): break
			
	def SEARCH_USER(self,user='default',terms=''):
		if not terms: return False
		start = self.getParamInt('start_index',1)
		uri = '/data/feed/api/user/%s?kind=photo&q=%s' % (user, terms)
		photos = self.api().GetFeed(uri,limit=self.max_per_page,start_index=start)
		self.addPhotos(photos,mode=4,terms=terms)
		return True
			
	def SEARCH_PICASA(self,terms=''):
		if not terms: return False
		start = self.getParamInt('start_index',1)
		uri = '/data/feed/api/all?q=%s' % (terms.lower())
		photos = self.api().GetFeed(uri,limit=self.max_per_page,start_index=start)
		self.addPhotos(photos,mode=5,terms=terms)
		return True
				
	def CONTACT(self,user,name):
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
			
		self.addDir(albums,self.addonPath('resources/images/albums.png'),url=user,mode=1)
		self.addDir(tags,self.addonPath('resources/images/tags.png'),url=user,mode=2)
		self.addDir(favs,self.addonPath('resources/images/contacts.png'),url=user,mode=3)
		self.addDir(search,self.addonPath('resources/images/search.png'),url=user,mode=4)
	
	def TAG(self,tag,user='default'):
		start = self.getParamInt('start_index',1)
		uri = '/data/feed/api/user/%s?kind=photo&tag=%s' % (user, tag.lower())
		photos = self.api().GetFeed(uri,limit=self.max_per_page,start_index=start)
		self.addPhotos(photos,mode=102,user=user)
  
	def ALBUM(self,aid,user='default'):
		start = self.getParamInt('start_index',1)
		uri = '/data/feed/api/user/%s/albumid/%s?kind=photo' % (user,aid)
		photos = self.api().GetFeed(uri,limit=self.max_per_page,start_index=start)
		self.addPhotos(photos,mode=101,user=user)
        
	
picasaPhotosSession()


