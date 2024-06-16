#-*- coding: UTF-8 -*-
import sys,os,requests,urllib,re,time,random,hashlib
from datetime import datetime
from tempfile import mktemp as mktemp
#from lxml import etree

history = set()

def usage():
	print(f'''{sys.argv[0]} [OPTION] <urls>...

[OPTION]
  -p thread   process
  -C dir      DIR 
  -h, --help  This message.

  url     http://mirrors.163.com/ubuntu/
  ''')

def MD5(str):
	md5 = hashlib.md5()
	md5.update(str.encode())
	return md5.hexdigest()

def html_href(html):
	try:
		return etree.HTML(html).xpath('//a//@href')
	except Exception as e: print(e); pass
	return []

# fast than etree.HTML.xpath
# <tr><td class="link"><a href="Release" title="Release">Release</a></td><td class="size">86.7 KiB</td><td class="date">26 Apr 2024 17:23:07 +0000</td></tr>
# <a href="ReleaseAnnouncement.html">ReleaseAnnouncement.html</a>                           19-Apr-2022 04:43    2651
def html_href2(html):
	try: return re.findall('<a href=["\'](.*?)["\'].*</a>', html, re.I)
	except Exception as e: print(e); pass
	return []
	#for o in a: print(a) exit(0)

def wget_notify(url):
	now = datetime.today()
	print(f'--{now:%Y-%m-%d %H:%M:%S}--  {url}', flush=True)

def web_dir(root, file, **kwargs):
	global history

	if 'filter' in kwargs:
		if re.search(kwargs['filter'], root): return

	if 'verbose' in kwargs:
		verbose = kwargs['verbose']
		if verbose: wget_notify(root)
	else: verbose = False

	if 'limit' in kwargs: limit = kwargs['limit']
	else: limit = 0xF

	if 'wait' in kwargs: wait = kwargs['wait']
	else: wait = [0, 3]

	if 'retry' in kwargs: retry = kwargs['retry']
	else: retry = 3

	if 'timeout' in kwargs: timeout = kwargs['timeout']
	else: timeout = (5, 10)

	header = {
	'Connection': 'keep-alive',
	'Pragma': 'no-cache',
	'Cache-Control': 'no-cache',
	'Accept': '*/*', 
	'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36'
	#'Origin': 'http://webapi.cninfo.com.cn',
	#'Referer': 'http://webapi.cninfo.com.cn/'
	}
	if root[-1]!='/':root=root+'/'
	while retry:
		retry-=1;
		try: html=requests.get(root, headers=header, timeout=(5, 10))
		except Exception as e:
			if retry<=0: print(e); return
			time.sleep(random.uniform(0.2,1.2)*wait[1])
			continue

		if 200!=html.status_code:
			if html.status_code==404 or retry<=0:
				print(f'ACCESS:{root}={html.status_code}')
				return
			time.sleep(random.uniform(0.4,2.4)*(1+wait[1]))
			continue
		break
	#print(html.status_code)
	#print(html.text)
	md5 = MD5(html.text)
	if md5 in history: return
	else: history.add(md5)
	if not (href := html_href2(html.text)): return
	r = urllib.parse.urlparse(root)
	netloc = r.netloc
	rpath = os.path.commonpath([r.path, r.path])
	rlen = len(rpath)
	for one in href:
		if one[0]=='#': continue
		ful = urllib.parse.urljoin(root, one);
		under = urllib.parse.urlparse(ful)
# ParseResult(scheme='https', netloc='pypi.tuna.tsinghua.edu.cn', 
# path='/packages/0e/52/e159a883cf486edd14803c8f905a8b045b67d3bf702d83fd62252f0f85ab/01_distributions-0.1.tar.gz', 
#params='', query='', fragment='sha256=42618310264e9290d47264f9f7053a7886b14303c7e39fea05e5d3b8d01e4e00')
		#print(under, limit);exit(0)
		if r.path == under.path: continue
		if len(under.params) or len(under.query): continue

		if (limit & 0x1) and under.netloc!=netloc: continue
		if (limit & 0x2) and len(under.path) <= rlen: continue
		if (limit & 0x4) and len(under.fragment): continue

		if (limit & 0x8) and rpath!=os.path.commonpath([r.path, under.path]): 
			continue
		match ful[-1]:
			case '/': 
				if wait[0]: time.sleep(random.uniform(0.15, 1.1)*wait[0])
				web_dir(ful, file, **kwargs)
				#if len(file): return
			case _: 
				ful = urllib.parse.unquote(ful)
				if verbose: wget_notify(ful)
				if ful not in file: file.add(ful)
	#~~for
# urllib.parse.unquote
# http://mirrors.163.com/ubuntu/dists/jammy/main/dep11/icons-48x48%402.tar.gz
# -->>
# http://mirrors.163.com/ubuntu/dists/jammy/main/dep11/icons-64x64@2.tar.gz

def wget(url, log):
	os.execlp('wget','wget','--no-show-progress','-T','10','-t','5', '-m','-i',url,'-o',log)

def download_process(url, log):
	if (pid := os.fork()):
		wget(url, log)
	else:
		print(f'wget -m -T10 -t 5 --no-show-progress -i {url} -o {log}={pid}')
	return pid

def write_to_file(fn, lines):
	with open(fn, 'w') as fp:
		for one in lines: fp.write(f'{one}\n')

def append_to_file(fn, lines):
	with open(fn, 'a+') as fp:
		for one in lines: fp.write(f'{one}\n')
	
if __name__ == '__main__':
	if False: ## just for debug
		with open(sys.argv[1], 'r') as fp:
			text = fp.read()
			for href in html_href2(text):
				print(href)
		exit(0)
	thread=3
	cwd=os.getcwd()
	# -C <dir>
	if '-C' in sys.argv:
		i = sys.argv.index('-C')
		try:
			os.chdir(sys.argv[i+1])
			del(sys.argv[i+1])
		except OSError as e:
			print(e)
			exit(e.errno)
		del(sys.argv[i])

	# -p <thread=1>
	if '-p' in sys.argv:
		i = sys.argv.index('-p')
		try:
			thread = int(sys.argv[i+1])
			del(sys.argv[i+1])
		except Exception as e: pass
		del(sys.argv[i])
	if not thread: thread=1
	if '--mirror' in sys.argv:
		sys.argv.remove('--mirror')
		mirror = True
	else: mirror = False

	if '-o' in sys.argv:
		i = sys.argv.index('-o')
		try:
			with open(sys.argv[i+1], 'w') as fp:
				del (sys.argv[i+1])
				os.dup2(fp.fileno(), sys.stdout.fileno())
		except Exception as e: pass
		del (sys.argv[i])

	if '--limit' in sys.argv:
		i = sys.argv.index('--limit')
		try:
			limit = int(sys.argv[i+1])
			del (sys.argv[i+1])
		except Exception as e: 
			limit = 0xF
		del (sys.argv[i])
	else: limit = 0xF

	if '-h' in sys.argv or '--help' in sys.argv or len(sys.argv) < 2: 
		usage();exit(0)
	#url='http://mirrors.163.com/ubuntu/'
	#url='https://mirrors.tuna.tsinghua.edu.cn/ubuntu/'
	file = set()
	#print(file)
	#exit(0)
	#url=sys.argv[1]
	#url='http://mirrors.163.com/ubuntu/dists/jammy/main/dep11'
	for one in sys.argv[1:]:
		try:
			with open(os.path.join(cwd, one), 'r') as fp:
				while line:=fp.readline():
					url=line[0:-1]
					#print(url)
					web_dir(url, file, verbose=True)
		except:
			#print(one)
			web_dir(one, file, verbose=True)
	#for attr in [file[i] for i in range(thread)]: 
	total = len(file)
	if not total: exit(0)
	file = list(file)
	if not mirror: exit(0)
	tmp = mktemp(prefix='web_dir_')
	write_to_file(f'{tmp}.ALL', file)

	count = int(total/thread)
	remain = int(total%thread)
	tasks = [count for x in range(thread)]
	tasks[0] += remain

	child = []
	start = 0;
	for i in range(0, thread):
		fn=f'{tmp}.{i}'
		end = start+tasks[i]
		write_to_file(fn, file[start:end])
		start = end;
		child.append(download_process(fn, f'{tmp}-logs.{i}'))

	while len(child):
		print(f'waiting {child}')
		pid, stat = os.wait()
		#print(f'{pid} exit({stat})')
		child.remove(pid)
