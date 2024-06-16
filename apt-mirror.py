#-*- coding: UTF-8 -*-
import sys, os, signal, select, glob, fcntl
import hashlib, random, requests, time
from datetime import datetime
#from lxml import etree
import urllib, re, json, gzip
import lzma as xz
wd = __import__('web-dir')
verbose = False
dot_json = []
g_weight = dict()

update_index= True
download_index = True
update_pool= True
download_pool = True

def check_default_setting():
	global update_index, download_index, update_pool 
	
	if update_index: update_index = not os.path.exists('index-urls.ALL')
	if download_index: download_index = not os.path.exists('content-urls.ALL')
	if update_pool: update_pool = not os.path.exists('content-urls.ALL')


def usage():
	print(f'''{sys.argv[0]} [OPTION] <apt-mirror.json>

[OPTION]
  --list-dist
  --dont-update-index
  --dont-download-index
  --dont-update-pool
  --dont-download-pool
  --sanity-check

  -h, --help  This message.
  ''')
	print('''apt-mirror.json:
{
	"thread": 3,
	"local": "/var/spool/apt-mirror/",
	"mirror": [{
		"sources": "http://mirrors.163.com/ubuntu/",
		"arch": "amd64",
		"deb": [
		{"jammy": ["main", "restricted", "multiverse", "universe"]},
		{"jammy-backports": ["main", "restricted", "multiverse", "universe"]},
		{"jammy-proposed": ["main", "restricted", "multiverse", "universe"]},
		{"jammy-security": ["main", "restricted", "multiverse", "universe"]},
		{"jammy-updates": ["main", "restricted", "multiverse", "universe"]}
		],
		"deb-src": [
		{"jammy": ["main", "restricted", "multiverse", "universe"]},
		{"jammy-backports": ["main", "restricted", "multiverse", "universe"]},
		{"jammy-proposed": ["main", "restricted", "multiverse", "universe"]},
		{"jammy-security": ["main", "restricted", "multiverse", "universe"]},
		{"jammy-updates": ["main", "restricted", "multiverse", "universe"]}
		]
	}, 
	{
		"sources": "https://mirrors.tuna.tsinghua.edu.cn/ubuntu/",
		"arch": ["amd64", "arm64"],
		"_arch": ["amd64", "arm64", "i386", "armhf", "ppc64el", "s390x"],
		"deb": [
		{"jammy": ["main", "restricted", "multiverse", "universe"]},
		{"jammy-backports": ["main", "restricted", "multiverse", "universe"]},
		{"jammy-proposed": ["main", "restricted", "multiverse", "universe"]},
		{"jammy-security": ["main", "restricted", "multiverse", "universe"]},
		{"jammy-updates": ["main", "restricted", "multiverse", "universe"]}
		],
		"deb-src": [
		{"jammy": ["main", "restricted", "multiverse", "universe"]},
		{"jammy-backports": ["main", "restricted", "multiverse", "universe"]},
		{"jammy-proposed": ["main", "restricted", "multiverse", "universe"]},
		{"jammy-security": ["main", "restricted", "multiverse", "universe"]},
		{"jammy-updates": ["main", "restricted", "multiverse", "universe"]}
		]
	}]
}''')

def apt_packages(fn, ubuntu, files):
	if verbose: print(fn)
	else: print(f'\r\033[K{fn}', end='', flush=True)
	try: 
		if re.search(r'\.gz$', fn):
			with gzip.open(fn, 'rt') as fp: text = fp.read()
		elif re.search(r'\.xz$', fn):
			with xz.open(fn, 'rt') as fp: text = fp.read()
		else:
			with open(fn, 'r') as fp: text = fp.read()
		if Filename:=re.findall('Filename: (.*)\n', text):
			#for one in Filename: print(one)
			files|=set(os.path.join(ubuntu, one) for one in Filename)
			#files.add(Filename[1])
	except Exception as e: 
		print(e)
		return OSError(e).errno
	return None

def apt_sources(fn, ubuntu, files):
	if verbose: print(fn)
	else: print(f'\r\033[K{fn}', end='', flush=True)
	try: 
		if re.search(r'\.gz$', fn):
			with gzip.open(fn, 'rt') as fp: text = fp.read()
		elif re.search(r'\.xz$', fn):
			with xz.open(fn, 'rt') as fp: text = fp.read()
		else:
			with open(fn, 'r') as fp: text = fp.read()
#		for block in re.findall('''^Directory: (.*?)
#.*?:
#.*?
#^Files:
#(.*?)
#^Checksums''', text, re.DOTALL|re.M):
		'''Directory: pool/universe/s/simplebackup
Files:
 a6526598b030379276427134b5a24586 1435 simplebackup_0.1.6-0ubuntu1.dsc
 3a8736e2f5ec459b7400e72163676b24 12952 simplebackup_0.1.6.orig.tar.gz
 4c49ed365e73933ef4f39ab146ccc763 1921 simplebackup_0.1.6-0ubuntu1.diff.gz
Directory: pool/universe/s/simplebayes
Package-List:
 python-simplebayes-doc deb doc optional arch=all
 python3-simplebayes deb python optional arch=all
Files:
 8cc0de3a52195a0e2a98b4c218a48e7f 2169 simplebayes_1.5.7-2.dsc
 22d7053320ddfbcea5a1d6e95d3a0f99 19260 simplebayes_1.5.7.orig.tar.gz
 95ab8b70ff1eba806feeeb7826fcf8aa 3004 simplebayes_1.5.7-2.debian.tar.xz'''
		for block in re.findall('''^Directory: (.*?)
^Files:
(.*?)
^Checksums''', text, re.DOTALL|re.M):
			directory = re.search('(.*)', block[0])[1]
			files |= set(os.path.join(ubuntu, directory, file) for 
			file in re.findall(r'\S+ \S+ (\S+)', block[1]))
	except Exception as e: 
		print(e)
		return OSError(e).errno
	return None

def parse_deb(root, arch, deb, dist, binary):
	for one in deb:
		jammy = list(one.keys())[0]
		if jammy[0]=='#' or jammy[0]=='_':
			deb.remove(one)
			continue
		value = one[jammy]
		dist.add(os.path.join(root, 'dists', jammy))
		gz = set(os.path.join(root, f'dists/{jammy}/{a}/binary-{arch}/Packages.gz') 
			for a in value)
		binary |= gz
		gz = set(os.path.join(root, f'dists/{jammy}/{a}/binary-{arch}/Packages.xz') 
			for a in value)
		binary |= gz
		gz = set(os.path.join(root, 
			f'dists/{jammy}/{a}/debian-installer/binary-{arch}/Packages.gz') 
			for a in value)
		binary |= gz
		gz = set(os.path.join(root, 
			f'dists/{jammy}/{a}/debian-installer/binary-{arch}/Packages.xz') 
			for a in value)
		binary |= gz

def parse_deb_src(root, deb_src, dist, src):
	for one in deb_src:
		jammy = list(one.keys())[0]
		if jammy[0]=='#' or jammy[0]=='_':
			deb_src.remove(one)
			continue
		value = one[jammy]
		dist.add(os.path.join(root, "dists", jammy))
		gz = set(os.path.join(root, f'dists/{jammy}/{a}/source/Sources.gz') 
			for a in value)
		src |= gz
		gz = set(os.path.join(root, f'dists/{jammy}/{a}/source/Sources.xz') 
			for a in value)
		src |= gz

def json_deb_source(js, arch, dists, deb, deb_src):
	#print(js)
	#print(type(js))
	root=js['sources']
	# root='http://mirror.163.com/ubuntu/'
	binary = set()
	src = set()
	dist = set()

	if 'deb' in js: parse_deb(root, arch, js['deb'], dist, binary)
	if 'deb-src' in js: parse_deb_src(root, js['deb-src'], dist, src)

	deb |= binary
	deb_src |= src
	dists |= dist

def prepare_work_dir(dirs):
	pool = os.path.join(dirs[0], 'pool')
	os.system(f'if [ ! -e {pool} ]; then mkdir -p {pool}; fi')

	dists = os.path.join(dirs[0], 'dists')
	os.system(f'if [ ! -e {dists} ]; then mkdir -p {dists}; fi')
	for ubuntu in dirs[1:]:
		#d = os.path.join(ubuntu, 'pool')
		# {ubuntu}=mirrors.tuna.tsinghua.edu.cn/ubuntu/
		# {pool} = mirrors.163.com/ubuntu/pool
		dst = f'{os.path.join(ubuntu, os.path.basename(pool))}'
		os.system(f'if [ ! -e ${dst} ]; then mkdir -p {ubuntu};ln -fs {pool} {ubuntu};fi')

		dst = f'{os.path.join(ubuntu, os.path.basename(dists))}'
		#os.system(f'if [ ! -e ${dst} ]; then mkdir -p {ubuntu};ln -fs {dists} {ubuntu};fi')
		os.system(f'if [ ! -e ${dst} ]; then mkdir -p {dst};fi')

def parse_one_mirror(js, urls, deb, deb_src):
	global g_weight

	if 'weight' not in js:js['weight']=1

	if 'arch' in js:
		if isinstance(js['arch'], list): arch = js['arch']
		else: arch = [js['arch'], ]
	else:
		arch='amd64'
		with os.popen('dpkg --print-architecture', 'r') as fp:
			arch=fp.read()[0:-1]
		arch = [arch, ]
		# force arch ->> list
	js['arch'] = arch

	mirror = re.search(r'.*:/+(.*?)/', js['sources'])[1]
	g_weight[mirror] = js['weight']

	for a in arch: json_deb_source(js, a, urls, deb, deb_src)

def json_mirror(js, urls, deb, deb_src):
	if not isinstance(js['mirror'], list):
		js['mirror'] = [js['mirror'],]

	cwd = os.getcwd()
	src=[]
	for one in js['mirror']:
		parse_one_mirror(one, urls, deb, deb_src)
		src.append(os.path.join(cwd, re.sub('.*:/+', '', one['sources'])))
	prepare_work_dir(src)

def log_is_finish(text):
	return True if re.findall('''^FINISHED --[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}--
.*?
^Downloaded: .*?''', text[-128:], re.DOTALL|re.M) else False
	
def downloading_http_from_log(fn):
	with open(fn, 'r') as fp:
		try:
			text = fp.read()[-2048:]
			if log_is_finish(text): return None
# --2024-03-09 03:52:00--  http://mirrors.163.com/ubuntu/pool/main/a/aalib/aalib_1.4p5-50build1.dsc
			http = re.findall('--[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}--  (.*)', text)
			if http: return http[-1]
		except Exception as e: print(e); pass
		#print(r[-1]); exit(0)
	return None

def find_local_pool():
	# 生成本地pool已经下载的文件列表
	down = set()
	find = r'find -L -wholename "*/ubuntu/pool/*" -type f'
	print(find)
	with os.popen(find, 'r') as fp:
		while (one:=fp.readline().rstrip('\n')):
		#./mirrors.tuna.tsinghua.edu.cn/... -> mirrors.tuna.tsinghua.edu.cn/...
			down.add(one[2:])
	return down

def load_continue_url_from(fn):
	url = set()
	with open(fn, 'r') as fp:
		print(f'-<< {fn}')
		while (one:=fp.readline().rstrip('\n')):
			# 去除本地已经下载的文件
			# https://mirror.163.com/ubuntu/pool/main/....  -> mirror.163.com/..
			if os.path.exists(re.sub('.*:/+', '', one)): continue
			url.add(one)
	# 分析日志得到正在下载可能还没有下载完成的文件
	# --2024-03-09 03:52:00--  http://mirrors.163.com/ubuntu/pool/main/a/aalib/aalib_1.4p5-50build1.dsc
	# Reusing existing connection to mirrors.163.com:80.
	# HTTP request sent, awaiting response... 304 Not Modified
	# File ‘mirrors.163.com/ubuntu/pool/main/a/aalib/aalib_1.4p5-50build1.dsc’ not modified on server. Omitting download.
	# wget -m -T 5 -t 10 -i content-urls.ALL --no-show-progress
	for one in glob.glob('content-logs.[0-9]*'):
		print(f'-<< {one}')
		if (last := downloading_http_from_log(one)):
			url.add(last)
	return url

def wget_what(text):
	http = re.findall('--[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}--  http(.*)', text)
	if http: return re.sub('.*/', '', http[-1])
	return None

def exec_wget(url):
	os.execlp('wget','wget','--random-wait', '--no-show-progress', '-m',
		'-T', f'{dot_json["wait"][0]}', '-t', f'{dot_json["wait"][1]}',
		'--wait', f'{dot_json["wait"][2]}', '-i', url)

def poll_walk_index(buf, child):
	if not buf: return []
	s = e = p = 0
	if child['buf']: buf = child['buf']+buf
	line = set()
	for b in buf:
		e = p
		p += 1
		if b==0xa: # '\n'
			if e == s:#empty line
				s = p; continue
			l = buf[s:e].decode('utf-8', 'ignore')
			l5 = l[0:5]
			if l5=='--<< ':
				child['fin'].add(l[5:])
			elif re.search('^http.*?:/+', l):
				line.add(l)
			s = p
		# b = 0xa
	# for b
	if s < len(buf): child['buf'] = buf[s:]
	else: child['buf']=None
	if 'ret' in child: child['ret'] += len(line)
	else: child['ret'] = len(line)

	ret = child['ret']
	fin = len(child['fin'])
	tot = len(child['array'])
	child['msg'] = f'{fin}/{tot}+{ret}'
	return line

def do_walk_index(i, url):
	href = set() 
	wd.write_to_file(f'jammy-urls.{i}', url)
	fn = f'index-urls.{i}' 
	fp = open(fn, 'w')
	for one in url: 
		new = set()
		w = dot_json['wait']
		wd.web_dir(one, new, wait=[0, w[2]], filter='/by-hash/')
		print(f'--<< {one}', flush=True)
		#new -= href
		href |= new
		for a in new: 
			print(a)
			fp.write(f'{a}\n')
	fp.close()

'''
--2024-06-01 15:37:08--  http://mirrors.163.com/ubuntu/dists/jammy-proposed/multiverse/i18n/Translation-is
Reusing existing connection to mirrors.163.com:80.
HTTP request sent, awaiting response... 200 OK
Server ignored If-Modified-Since header for file ‘mirrors.163.com/ubuntu/dists/jammy-proposed/multiverse/i18n/Translation-is’.
You might want to add --no-if-modified-since option.
'''
def wget_ignored_if_modified(text):
	return not not re.search('^Server ignored If-Modified-Since header', text,
		re.DOTALL|re.M)

def wget_omit(text):
	return not not re.search('^File .* Omitting download.$', text, 
		re.DOTALL|re.M)

def wget_giving_up(text):
	return not not re.search('^.*Giving up.$', text, re.DOTALL|re.M)

def wget_saved(text):
	return not not re.search(r'^[0-9]{4}-[0-9]{2}-[0-9]{2} .* saved \[.*\]$',
		text, re.DOTALL|re.M)

def wget_last_saving(fn):
	try:
		with open(fn, 'r', encoding="utf-8",errors='ignore') as fp:
			pos = os.stat(fn).st_size
			if pos > 2048: fp.seek(pos-2048)
			text = fp.read()
# 00000000: 5361 7669 6e67 2074 6f3a 20e2 8098 6d69  Saving to: ...mi
# Saving to: ‘mirrors.163.com/ubuntu/pool/main/l/linux-hwe-6.5/linux-source-6.5.0_6.5.0-27.28~22.04.1_all.deb’
			block = re.findall(r'''
^--[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}--  (.*?)
.*
^Length:\s+(.*?)\s+.*
^Saving to: ‘(.*?)’''', text, re.DOTALL|re.M)
			if block:
				block = block[-1]
				return block[0], int(block[1]), block[2]
	except Exception as e: print(e); pass
	return None, 0, None

def wget_downloading(child):
	fn = f'{child["task"]}-logs.{child["index"]}'
	_, length, fn = wget_last_saving(fn)
	if fn and length:
		flen = os.stat(fn).st_size
		child['msg'] = f'{(flen/length):.2%}@{length}'

def poll_wget_log(buf, child):
	if not buf:
		wget_downloading(child)
		return []
	if verbose: print(buf.decode('utf-8', 'ignore'))
	if child['buf']: buf = child['buf']+buf
	text = buf.decode('utf-8', 'ignore')
	pos = 0
	fin = set()
	while (m := re.search('''^--[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}--  (.*?)
(.*?)\n\n''', text[pos:], re.DOTALL|re.M)):
		url = m[1]
		msg = m[2]
		if wget_omit(msg) or wget_saved(msg) or wget_ignored_if_modified(msg):
			fin.add(url)
		pos += m.span(0)[1]
	# while()
	if pos < len(text): child['buf']=text[pos:].encode()
	else: child['buf']=None

	if fin: child['fin'] |= fin

	fcc = len(child['fin'])
	tot = len(child['array'])
	child['msg'] = f'{fcc}/{tot}={fcc/tot:.2%}'
	return fin

def create_child(child, i, array, doit, task):
	r,w = os.pipe()
	#r,w = os.pipe2(os.O_NONBLOCK)
	if (pid := os.fork()) == 0: 
		os.dup2(w, 1)
		os.dup2(w, 2)
		# close all unused fd
		for j in range(3, w+1): os.close(j)
		doit(i, array); exit(0)
	os.close(w)
	if verbose:print(f'\r{pid} started', flush=True)

	fcntl.fcntl(r, fcntl.F_SETFL, fcntl.fcntl(r, fcntl.F_GETFL) \
		| os.O_NONBLOCK)

	child[r]={'task':task, 'index':i, 'pid':pid, 'buf':None,
		'array':array, 'fin':set(), 'msg':None, 'log':None}

	if task: child[r]['log'] = os.open(f'{task}-logs.{i}', 
		os.O_WRONLY|os.O_APPEND|os.O_CREAT, 0o640)

def wget_can_stop(child):
	fn = f'{child["task"]}-logs.{child["index"]}'
	with open(fn, 'r', encoding="UTF-8",errors='ignore') as fp:
		pos = os.stat(fn).st_size
		if pos > 128: fp.seek(pos-128)
		text = fp.read(128)
		return not not re.search('^Saving to:', text, re.M)
	return True


def try_stop_child(child):
	dead = True
	for i in child:
		if not (pid:=child[i]['pid']): continue

		if wget_can_stop(child[i]): os.kill(pid, signal.SIGSTOP)
		else: dead = False
	return dead

def frozen(child, rest):
	i = 0
	s = try_stop_child(child)
	while i<rest:
		i += 5
		if not s: s = try_stop_child(child)
		print(f'\r\033[K {i}/{rest}', end='', flush=True)
		time.sleep(random.uniform(0.8, 1.2)*5)

	for i in child:
		if (pid:=child[i]['pid']): os.kill(pid, signal.SIGCONT)

def read_from_child(a, child, poll, aset):
	buf = None
	try:
		while (b := os.read(a, 4096)):
			if buf: buf += b
			else: buf = b
		# while(0)
	except OSError as e:
		#if e.errno == errno.EAGAIN
		pass

	if buf:
		if child[a]['log']: os.write(child[a]['log'], buf)
		return poll(buf, child[a])
	else:
		pid, _= os.waitpid(-1, os.WNOHANG)
		for i in child:
			if child[i]['pid']==pid:
				aset.remove(i)
				os.close(i)
				if child[i]['log']: os.close(child[i]['log'])
				child[i]['pid']=None
				break # break for(i)
		##for(i)
	return []

def parallel_doit(thread, array, doit, poll, **kwargs):
	if 'task' in kwargs: task = kwargs['task']
	else: task = None

	if 'rest' in kwargs: rest = kwargs['rest']
	else: rest = [0, 0]
	total = len(array)
	count = int(total/thread)
	odd = total-(count*(thread-1))
	start = odd
	child = dict()

	# create first task
	create_child(child, 0, array[0:odd], doit, task)

	# create remain tasks
	for i in range(1, thread):
		if start>= total: break
		create_child(child, i, array[start:start+count], doit, task)
		start += count
	# wait all child exit

	result = set()
	aset = list(child)
	carry = 0
	restc = 0
	while aset:
		rs, _, _ = select.select(aset, [], [], 10)
		for a in child:
			if a in rs:
				ret = read_from_child(a, child, poll, aset)
				cc = len(ret)
				if cc>0:
					restc += cc
					carry += cc
					result |= ret
			##if a in rs
			else:
				if (pid:=child[a]['pid']): poll(None, child[a])
		# for a in child

		print('\r\033[K', end='', flush=True)
		for a in child:
			pid = child[a]['pid']
			msg = child[a]['msg']
			print(f'{pid}:{msg}', end=' ', flush=True)

		if rest[0] and (restc>rest[0]):
			print(f'| {carry}/{total}={carry/total:.2%}', flush=True)
			frozen(child, rest[1])
			restc = 0
		else: print(f'| {carry}/{total}={carry/total:.2%}', end='', flush=True)
	# while(aset)
	print('', flush=True)
	return result

def weight_of_url(url):	
	global g_weight
	mirror = re.search(r'.*:/+(.*?)/', url)[1]
	if mirror not in g_weight: g_weight[mirror] = 1
	return g_weight[mirror]

# two > one True or False
def one_or_two(one, two):
	one = weight_of_url(one)
	two = weight_of_url(two)
	return random.randint(1, one+two)>one
	
def uniq_urls(pattern, url, verbose=True):
	global dot_json, g_weight
	# remove the same file in pool/**
	uni = dict()
	hint=('-','\\','|','/')
	c=i=0
	t = len(url)
	cpy = url.copy()
	url.clear()
	for one in cpy:
		if verbose and (i:=i+1)%256==0:
			print(f'\r\033[K{hint[int(i/256%4)]} {i}/{t} {c}', end='', flush=True)
		path = re.sub(pattern, '', one)
		if path not in uni: 
			c+=1
			uni[path] = one
			url.add(one)
		# NOTE:urls文件重复,可以选择从不同的mirrors下载
		elif one_or_two(uni[path], one):
			url.remove(uni[path])
			uni[path] = one
			url.add(one)
		# else
	#~~for one
	return url

# 将列表排序之后分散
def distribute_index(index, n):
	index.sort()
	total = len(index)
	group = len(index)//n
	odd = total - group*n
	if odd: odd = index[-odd:]
	else: odd = []

	for one in zip(*list(index[i*n:(i+1)*n] for i in \
		range(0, group))): odd.extend(one)
	index.clear()
	index.extend(odd)
	return index

def parallel_wget(thread, array, task):
	doit = lambda i, url:  (exec_wget(fn) \
		if (wd.write_to_file((fn:=f'{task}-wget.{i}'), url) or True) \
		else False)

	parallel_doit(thread, array, doit, poll_wget_log, task=task, 
			rest = dot_json['rest'])

'''
Index of /ubuntu/dists/noble/main
[ICO]	Name	Last modified	Size
[PARENTDIR]	Parent Directory	 	-
[DIR]	binary-amd64/	2024-04-25 15:10	-
[DIR]	binary-i386/	2024-04-25 15:10	-
[DIR]	cnf/	2024-01-04 19:34	-
[DIR]	debian-installer/	2023-10-23 22:49	-
[DIR]	dep11/	2023-11-12 23:44	-
[DIR]	dist-upgrader-all/	2024-04-21 12:13	-
[DIR]	i18n/	2024-04-25 15:10	-
[DIR]	signed/	2024-01-04 23:38	-
[DIR]	source/	2024-04-25 15:10	-
'''
def jammy_skel(main, arch):
	index = set()
	w = dot_json['wait']
	'''Index of /ubuntu/dists/noble/main/binary-amd64
	[ICO]	Name	Last modified	Size
	[PARENTDIR]	Parent Directory	 	-
	[   ]	Packages.gz	2024-04-25 15:11	1.7M
	[   ]	Packages.xz	2024-04-25 15:11	1.3M
	[   ]	Release	2024-04-25 15:11	95
	[DIR]	by-hash/	2023-10-24 02:57	- '''
	index |= set(os.path.join(main, f'binary-{a}/{f}') for a in arch \
			for f in ('Packages.gz', 'Packages.xz', 'Release'))

	'''Index of /ubuntu/dists/noble/main/cnf
	[ICO]	Name	Last modified	Size
	[PARENTDIR]	Parent Directory	 	-
	[   ]	Commands-amd64.xz	2024-01-04 18:21	30K
	[   ]	Commands-i386.xz	2024-01-04 18:29	20K
	[DIR]	by-hash/	2024-01-04 19:19	-'''
	index |= set(os.path.join(main, f'cnf/Commands-{a}.xz') for a in arch)
	'''Index of /ubuntu/dists/noble/main/debian-installer/binary-amd64
	[ICO]	Name	Last modified	Size
	[PARENTDIR]	Parent Directory	 	-
	[   ]	Packages.gz	2024-04-25 15:11	40
	[   ]	Packages.xz	2024-04-25 15:11	64
	[DIR]	by-hash/	2023-10-24 02:57	-'''
	index |= set(os.path.join(main, f'debian-installer/binary-{a}/{f}') \
			for a in arch for f in ('Packages.gz', 'Packages.xz'))

	'''
	Index of /ubuntu/dists/noble/main/dep11
	CID-Index-amd64.json.gz
	Components-amd64.yml.gz
	Components-amd64.yml.xz
	icons-48x48.tar.gz	
	icons-48x48@2.tar.gz
	icons-64x64.tar.gz
	icons-64x64@2.tar.gz
	icons-128x128.tar.gz
	icons-128x128@2.tar.gz'''
	index |= set(os.path.join(main, f'dep11/{f}') \
	for f in ('icons-48x48.tar.gz',
		'icons-48x48@2.tar.gz', 'icons-64x64.tar.gz',
		'icons-64x64@2.tar.gz', 'icons-128x128.tar.gz',
		'icons-128x128@2.tar.gz'))
	index |= set(os.path.join(main, f'dep11/{f}') \
		for f in \
		tuple(f'CID-Index-{a}.json.gz' for a in arch)+\
		tuple(f'Components-{a}.yml.gz' for a in arch)+\
		tuple(f'Components-{a}.yml.xz' for a in arch))

	'''Index of /ubuntu/dists/noble/main/dist-upgrader-all'''
	res = set()
	print(os.path.join(main, 'dist-upgrader-all'))
	wd.web_dir(os.path.join(main, 'dist-upgrader-all'), \
		res, wait=[0, w[2]], filter='/by-hash/')
	index |= res

	'''Index of /ubuntu/dists/noble/main/i18n
	Index of /ubuntu/dists/noble/main/signed'''
	res = set()
	print(os.path.join(main, 'i18n'))
	wd.web_dir(os.path.join(main, 'i18n'),	\
		res, wait=[0, w[2]], filter='/by-hash/')
	index |= res

	print(os.path.join(main, 'signed'))
	wd.web_dir(os.path.join(main, 'signed'), \
		res, wait=[0, w[2]], filter='/by-hash/')
	index |= res

	'''Index of /ubuntu/dists/noble/main/source
[   ]	Release	2024-04-25 15:11	96
[   ]	Sources.gz	2024-04-25 15:11	1.6M
[   ]	Sources.xz	2024-04-25 15:11	1.3M '''
	index |= set(os.path.join(main, f'source/{f}') \
		for f in ('Release', 'Sources.gz', 'Sources.xz'))
	return index

def index_skel(js):
	index = set()
	arch = js['arch']
	mirror = js['sources'] # http://mirror.163.com/ubuntu/
	for deb in js['deb']:
		jammy = list(deb.keys())[0]
		loc = os.path.join(mirror, f'dists/{jammy}')
		index |= set(os.path.join(loc, f'Contents-{x}.gz') for x in arch)
		index |= set(os.path.join(loc, f'{x}') for x in \
			('InRelease','Release', 'Release.gpg'))
		'''
Index of /ubuntu/dists/noble
Contents-amd64.gz
Contents-i386.gz
InRelease
Release	
Release.gpg'''
		for main in deb[jammy]:
			index |= jammy_skel(os.path.join(loc, main), arch)
		'''
[DIR]	main/
[DIR]	multiverse/	
[DIR]	restricted/
[DIR]	universe/'''
	##for deb
	return index

def do_update(thread, dists, packages_gz, sources_gz):
	if len(sys.argv)>=2: pattern = sys.argv[1]
	else: pattern = None

	index = set()
	for a in dot_json['mirror']:
		if (not pattern) or (not re.search(pattern, a['sources'])): continue
		print('updating', a['sources'])
		index |= index_skel(a)

	md5 = wd.MD5(str(datetime.now()))[-4:]
	fn = f'update_index.{md5}'
	wd.write_to_file(fn, index)
	print(f'{len(index)} ->> {fn}')
	parallel_wget(thread, list(index), md5)

def down_index(dists, thread):
	if update_index:
		distribute_index(dists, thread)
		index = set()
		for a in dot_json['mirror']:
			index |= index_skel(a)
		#index = parallel_doit(thread, dists, do_walk_index, poll_walk_index)
		if index: 
			#wd.write_to_file('index-urls.AL0', list(index))
			#uniq_urls('.*?/dists/', index)
			wd.write_to_file('index-urls.ALL', list(index))
	elif download_index:
		index = set()
		with open('index-urls.ALL', 'r') as fp: fread_lines(fp, index)
	if download_index and index:
		#index = distribute_index(list(index), thread)
		parallel_wget(thread, list(index), 'index')

def down_pool(urls, thread):
	parallel_wget(thread, urls, 'content')

def parse_package(packages_gz, sources_gz, fn):
	# start to parse Packag.gz/Sources.gz/
	urls = set()
	if (not update_pool) and fn and os.path.exists(fn):
		with open(fn, 'r') as fp:
			print(f'-<< {fn}')
			while (one:=fp.readline().rstrip('\n')):
				urls.add(one)
		return urls

	#uniq_urls('.*?:/+.*?/', packages_gz, False)
	for one in packages_gz: 
		# http://...163.com/ubuntu/dist/../Packages.gz
		# --> mirror.163.com/ubuntu/../Packages.gz
		apt_packages(re.sub('.*:/+', '', one), \
			re.search('(.*)dists/', one)[1], urls)
	#uniq_urls('.*?:/+.*?/', sources_gz, False)
	for one in sources_gz: 
		apt_sources(re.sub('.*:/+', '', one), \
			re.search('(.*)dists/',one)[1], urls)

	# start to download pool/*
	fn0 = 'content-urls.AL0'
	print(f'\n->> {fn0}')
	wd.write_to_file(fn0, list(urls))
	uniq_urls('.*?/pool/', urls)

	if fn:
		print(f'\n->> {fn}')
		wd.write_to_file(fn, list(urls))
	return urls

def parse_json(dists, packages_gz, sources_gz):
	for fn in ('./apt-mirror.json', '/etc/apt-mirror.json'):
		if not os.path.exists(fn): continue
		with open(fn, 'r') as fp:
			js = json.load(fp)
			if 'rest' not in js: js['rest'] = [0, 0]
			if 'thread' not in js: js['thread'] = 3
			if 'wait' not in js: js['wait']=[5,8,2.8]
			if 'local' in js: os.chdir(js['local'])
			json_mirror(js, dists, packages_gz, sources_gz)
			return js
	return None

# http://mirrors.163.com/ubuntu/dists....
# ->> mirrors.163.com/ubuntu/dists....
def load_index_from(fn):
	res = set()
	with open(fn, 'r') as fp:
		print(f'-<< {fn}')
		while (one:=fp.readline().rstrip('\n')):
			res.add(re.sub('.*:/+', '', one))
	return res

def clean_index(thread, dists, packages_gz, sources_gz):
	# 1. del ubuntu/dists/jammy...
	junk=set()
	# https://mirrors.163.com/ubuntu/dists/jammy -> jammy
	dists = set(map(lambda x:re.sub('.*/dists/', '', x), dists))
	for one in glob.glob('*/ubuntu/dists/*'):
		a = re.sub('.*/dists/', '', one)
		if a not in dists: 
			dists.add(a)
			junk.add(one)

	# 2. del junk file in dists/jammy/main/by-hash/fh3...	
	if not os.path.exists('index-urls.ALL'):
		# create index-urls.ALL
		download_index = False
		update_index = True
		down_index(list(dists), thread)

	index = load_index_from('index-urls.ALL')

	find = r'find -wholename "*/ubuntu/dists/*" -type f'
	if verbose: print(find)
	tot = d = 0
	with os.popen(find, 'r') as fp:
		while (fn:=fp.readline().rstrip('\n')):
			tot += 1
			#./mirrors.163.com/ubuntu/dists/jammy-security/multiverse/dep11/CID-Index-amd64.json.gz
			# ->> mirrors.163.com/ubuntu/dists/jammy-security/multiverse/dep11/CID-Index-amd64.json.gz
			#one = re.sub('.*/dists/', '', fn)
			if fn[2:] not in index:
				d += 1
				junk.add(fn)
	print(f'{tot}-{d} = {len(index)}')
	wd.write_to_file('clean-index.ALL', junk)
	return 
	md5 = wd.MD5(str(datetime.now()))[-4:]
	if len(junk):
		# backup
		os.system(f'tar -czf clean_index{md5}.tgz {junk}')
		with os.popen('cat | xargs rm -rf','w') as rm:
			rm.write(f'{junk}\n')

def load_pool_from(fn):
	res = set()
	with open(fn, 'r') as fp:
		print(f'-<< {fn}')
		while (one:=fp.readline().rstrip('\n')):
			res.add(re.sub('.*/pool/', '', one))
	return res

def clean_pool(thread, dists, packages_gz, sources_gz):
	update_pool = True

	# force reparse local packages.gz & sources.gz
	# -> content-urls.ALL
	down = set()
	for one in parse_package(packages_gz, sources_gz, None):
		down.add(re.sub('.*/pool/', '', one))
	wd.write_to_file('content-urls.ALX', down)

	find = r'find -wholename "*/ubuntu/pool/*" -type f'
	# print(find)
	a = len(down)
	b = d = 0
	junk = set()
	with os.popen(find, 'r') as fp:
		#md5 = wd.MD5(str(datetime.now()))[-4:]
		#cpio = f'cpio -o -H newc|gzip -9 >clean_pool{md5}.cpio.gz'
		#try: cpio = os.popen(cpio, 'w')
		#except Exception as e: print(e);return

		while (fn:=fp.readline().rstrip('\n')):
			one = re.search(r'.*/pool/(.*)', fn)
			if not one: continue
			b += 1
			if one[1] not in down: 
				#cpio.write(f'{fn}\n')
				junk.add(fn)
				d += 1
			else: down.add(one[1])
			# if one in down
		#cpio.close()
		#rm = f'gzip -dc clean_pool{md5}.cpio.gz|cpio -t|xargs rm'
		# print(rm)
		# os.system(rm)
	## with
	wd.write_to_file('clean-pool.ALL', junk)
	print(f'\n{b}-{a} = {d} deleted')
	#if d==0: return
	#rm = r'find -wholename "*/ubuntu/pool/*" -type d -empty -exec rmdir {} \; 2>/dev/null'
	# print(rm)
	#os.system(rm)

'''
1. 读取content-urls.ALL中的下载资源
2. 去除已经下载到本地的资源
3. 增加日志中正在下载的资源
4. 开始继续下载
'''

def index_continue(thread, dists, packages_gz, sources_gz):
	down = set()
	local = set()

	find = r'find -wholename "*/ubuntu/dists/*" -type f'
	if verbose: print(find)
	with os.popen(find, 'r') as fp:
		while (one:=fp.readline().rstrip('\n')[2:]):
			local.add(one)
	#print(f'local={len(local)}')

	if not os.path.exists('index-urls.ALL'):
		os.system('cat index-urls.[0-9]* >index-urls.ALL')
	with open('index-urls.ALL', 'r') as fp:
		while (one:=fp.readline().rstrip('\n')):
			if re.sub('.*:/+', '', one) not in local: 
				down.add(one)
	#print(len(down))

	for one in glob.glob('index-logs.[0-9]*'):
		print(f'-<< {one}')
		if (last := downloading_http_from_log(one)):
			down.add(last)
	#print(down); exit(0)
	parallel_wget(thread, list(down), 'index')
	return 0

def fread_lines(fp, line):
	while (one:=fp.readline().rstrip('\n')): line.add(one)
	return line

def list_file_of_dist(mirror, dist, pool):
	dir = re.sub(r'.*//', './', dist)
	os.system(f'find {dir} -type f')

	gz = set()

	find = f'find {dir} -name Packages.gz -or -name Packages.xz -type f'
	with os.popen(find) as fp: fread_lines(fp, gz)
	for one in gz: apt_packages(one, mirror, pool)

	gz = set()
	find = f'find {dir} -name Sources.gz -or -name Sources.xz -type f'
	with os.popen(find) as fp: fread_lines(fp, gz)
	for one in gz: apt_sources(one, mirror, pool)

def wget_url(thread, dists, packages_gz, sources_gz):
	global g_cdir
	try:
		if len(sys.argv)>=2: 
			fp = open(os.path.join(g_cdir, sys.argv[1]), 'r')
		else: fp = os.fdopen(0)
	except Exception as e:print(e);exit(0)
	md5 = wd.MD5(str(datetime.now()))[-4:]
	url = set()
	while (a:=fp.readline().rstrip('\n')): url.add(a)
	fp.close()
	parallel_wget(thread, list(url), md5)

# down load mirror
# http://archive.ubuntu.com/ubuntu/dists/jammy/
# --down-mirror archive.ubuntu.com/ubuntu/dists/noble-proposed
def down_mirror(thread, dists, packages_gz, sources_gz):
	if len(sys.argv)>=2:
		mirror = sys.argv[1]
		del(sys.argv[1])
	else: mirror = None

	res = set()
	w = dot_json['wait']
	for a in dists:
		if mirror and not re.search(mirror, a): continue
		wd.web_dir(a, res, wait=[0, w[2]], filter='/by-hash/')
	#for a in res: print(a)
	fn = f'down_mirro.{wd.MD5(str(datetime.now()))[-4:]}'
	wd.write_to_file(fn, res)
	print(f'{len(res)} ->> {fn}')
	return 0

def list_dist(thread, dists, packages_gz, sources_gz):
	with os.popen('find -wholename "*/ubuntu/pool" -type d') as fp:
		mirror = list(fread_lines(fp, set()))[0]
		mirror = re.sub('/pool', '', mirror)

	if len(sys.argv)<=2:
		for one in dists: print(os.path.basename(one))
		return
	pool = set()
	for key in sys.argv[2:]:
		for one in dists:
			if key in os.path.basename(one):
				list_file_of_dist(mirror, one, pool)
	for one in pool: print(one)

def omit_or_saved_from_log(fn):
	remain = None
	with open(fn, 'r') as fp:
		while (text := fp.read(4096*1024)):
			if remain: text = remain+text
			start = 0
			while (m := re.search('''^--[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}--  (.*?)
(.*?)\n\n''', text[start:], re.DOTALL|re.M)):
				if wget_omit(m[2]) or wget_saved(m[2]) or wget_ignored_if_modified(m[2]): 
				# (try: 2)  https://mirrors.huaweicloud.com/ubuntu/ubuntu/
					http = re.sub(r'^\(.*\)\s+', '', m[1])
					yield http
				start += m.span(0)[1]
			# while()
			remain = text[start:]
		#while fp.read
	# with
	return None

def giving_block(fn):
	remain = None
	i = 0
	with open(fn, 'r') as fp:
		while (text := fp.read(4096*1024)):
			if remain: text = remain+text
			start = 0
			i += 1
			while (m := re.search('''^--[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}--  (.*?)
(.*?)\n\n''', text[start:], re.DOTALL|re.M)):
				if wget_giving_up(m[2]):
					# (try: 2)  https://mirrors.huaweicloud.com/ubuntu/ubuntu/
					http = re.sub(r'^\(.*\)\s+', '', m[1])
					yield http
				start += m.span(0)[1]
			# while()
			remain = text[start:]
		#while fp.read
	# with
	return None

def giving_from_log():
	giving = set()
	for fn in glob.glob('content-logs.[0-9]*'):
		print(f'\r\033[K<<- {fn}', end='')
		for http in giving_block(fn):
			giving.add(http)
	return giving

def do_missing_down(thread):
	with open('miss.ALL', 'r') as fp:
		fread_lines(fp, (urls:= set()))
		if not urls: return
		parallel_wget(thread, list(urls), 'miss')

def MD5_File(fn):
	try: fd = os.open(fn, os.O_RDONLY)
	except Exception as e:
		print(e)
		return None, None

	md5 = hashlib.md5()
	while (buf := os.read(fd, 2048)):
		md5.update(buf)
	os.close(fd)
	return os.stat(fn).st_size, md5.hexdigest()

def Release_MD5Sum_Check(http, release, err):
	dir = os.path.dirname(release)
	with open(release, 'r') as fp:
		text = fp.read()
		MD5Sum = re.search('''^MD5Sum:
(.*)
SHA1:''', text, re.DOTALL|re.M)
		#print(release, MD5Sum[1]);exit(0)
		if not MD5Sum: return
		for md5, size, ff in re.findall(r' (\S+)\s+(\S+) (\S+)', MD5Sum[1]):
			fn = os.path.join(dir, ff)
			if not os.path.exists(fn): continue
			size1, md51 = MD5_File(fn)
			print(f'\r\033[K{fn} ', end='', flush=True)
			if (not int(size)==size1) or (not md5 == md51):
				#print(fn, size, md5, size1, md51, "ERROR")
				print('ERR', end='', flush=True)
				err.add(os.path.join(http, ff))
			else: print('OK', end='', flush=True)

def sanity_check(_, jammy, packages_gz, sources_gz):
	if len(sys.argv) >= 2: pattern = sys.argv[1]
	else: pattern = None

	err = set()
	for http in jammy:
		if pattern and not re.search(pattern, http): continue
		fn = os.path.join(re.sub('.*:/+', '', http), 'Release')
		Release_MD5Sum_Check(http, fn, err)
	if err:
		md5 = wd.MD5(str(datetime.now()))[-4:]
		fn = f'sanity_error.{md5}'
		wd.write_to_file(fn, err)
		print(f'\r\033[K{len(err)} ->> {fn}')
		return False
	else:
		print('\r\033[KAll OK')
		return True
	#return False if err else True

def miss_check(_, jammy, packages_gz, sources_gz):
	if (not os.path.exists('index-urls.ALL')) or \
		(not os.path.exists('content-urls.ALL')):
		print('index-urls.ALL or content-urls.ALL missing')
		return False
	miss = set()
	# 1. check file in index-urls.ALL
	index = set()
	urls = set()
	print('<<- index-urls.ALL')
	with open('index-urls.ALL', 'r') as fp: fread_lines(fp, urls)

	for http in urls:
		if not os.path.exists(re.sub('.*:/+', '', http)):
			index.add(http)
	if index:
		print('\r\033[K->> index.miss', len(index))
		wd.write_to_file('index.miss', index)
		miss |= index

	# 2. check Packages.gz Sources.gz

	gz = set()
	for one in (packages_gz|sources_gz):
		fn = re.search('.*:/+(.*)', one)
		if not fn or (not os.path.exists(fn[1])):
			gz.add(one)
	if gz:
		print('\r\033[K->> packages.miss', len(gz))
		wd.write_to_file('packages.miss', gz)
		miss |= gz

	# 3. check down pool
	pool = set()
	urls = set()
	with open('content-urls.ALL', 'r') as fp: fread_lines(fp, urls)

	for http in urls:
		# check if downloaded
		if not os.path.exists(re.sub('.*:/+', '', http)): 
			pool.add(http)
	if pool:
		print('\r\033[K->> pool.miss', len(pool))
		wd.write_to_file('pool.miss', pool)
		miss |= pool

	# giving up urls
	if (giving := giving_from_log()):
		print('\r\033[K->> giving.miss', len(giving))
		wd.write_to_file('giving.miss', giving)
		miss |= giving

	if miss: 
		print('\r\033[K->> miss.ALL', len(miss))
		print(f'MISSING:{len(index)=}', f'{len(gz)=}+{len(pool)=}', \
			f'{len(giving)=}={len(miss)=}', sep='+')
		wd.write_to_file('miss.ALL', miss)
		return False
	else: 
		rm = 'rm -f index.miss packages.miss pool.miss. miss.ALL'
		os.system(rm)
		#if os.path.exists('miss-urls.ALL'): os.remove('miss-urls.ALL')
		print("\r\033[KALL DOWN")
	return True

def test(fn):
	child={'task':'wget', 'index':0, 'pid':9527, 'buf':None,
		'array':[1,2,3,4], 'fin':set(), 'msg':None, 'log':None}

	fd = os.open(fn, os.O_RDONLY)
	while (buf := os.read(fd, 2048)):
		poll_wget_log(buf, child)

if __name__ == '__main__':
	do_then_exit = None
	if '--verbose' in sys.argv:
		sys.argv.remove('--verbose');
		verbose = True

	# --apt-sources
	if '--apt-sources' in sys.argv:
		i = sys.argv.index('--apt-sources')
		urls=set()
		for fn in sys.argv[i+1:]:
			apt_sources(fn, '', urls)
		for one in urls: print(one)
		exit(0)
	# --apt-packages
	if '--apt-packages' in sys.argv:
		i = sys.argv.index('--apt-packages')
		urls=set()
		for fn in sys.argv[i+1:]:
			apt_packages(fn, '', urls)
		for one in urls: print(one)
		exit(0)

	if '--dont-update-index' in sys.argv:
		sys.argv.remove('--dont-update-index')
		update_index=False
	if '--dont-download-index' in sys.argv:
		sys.argv.remove('--dont-download-index')
		download_index=False
	if '--dont-update-pool' in sys.argv:
		sys.argv.remove('--dont-update-pool')
		update_pool=False
	if '--dont-download-pool' in sys.argv:
		sys.argv.remove('--dont-download-pool')
		download_pool=False

	if '--clean-index' in sys.argv:
		sys.argv.remove('--clean-index')
		do_then_exit=clean_index

	if '--clean-pool' in sys.argv:
		sys.argv.remove('--clean-pool')
		do_then_exit=clean_pool

	if '--miss-check' in sys.argv:
		sys.argv.remove('--miss-check')
		do_then_exit=miss_check

	if '--sanity-check' in sys.argv:
		sys.argv.remove('--sanity-check')
		do_then_exit=sanity_check

	if '--update' in sys.argv:
		sys.argv.remove('--update')
		do_then_exit=do_update

	if '--down-miss' in sys.argv:
		sys.argv.remove('--down-miss')
		do_then_exit=lambda thread, dists, packages_gz, sources_gz: \
			(0, do_missing_down(thread))[0]

	if '--continue-pool' in sys.argv:
#从content-urls.ALL中读取需要下载的资源,
#去除已经下载到本地的
#保险起见将在日志文件中正在下载的文件重新下载一遍
		sys.argv.remove('--continue-pool')
		do_then_exit = lambda thread, dists, packages_gz, sources_gz: ( \
			down_pool(list(urls), thread) \
			if (urls:=load_continue_url_from('content-urls.ALL')) else \
			(0, print("ALL DONE"))[0])

	if '--parse-package-only' in sys.argv:
		sys.argv.remove('--parse-package-only')
		do_then_exit = lambda thread, dists, packages_gz, sources_gz:	\
		 	(0, parse_package(packages_gz, sources_gz, 'content-urls.ALL'))[0]

	if '--continue-index' in sys.argv:
		sys.argv.remove('--continue-index')
		do_then_exit = index_continue

	if '--list-dist' in sys.argv:
		do_then_exit = list_dist
		sys.argv.remove('--list-dist')

	if '--down-mirror' in sys.argv:
		sys.argv.remove('--down-mirror')
		do_then_exit = down_mirror

	if '--update-index' in sys.argv:
		sys.argv.remove('--update-index')
		do_then_exit = do_update

	if '--wget-url' in sys.argv:
		global g_cdir
		g_cdir = os.getcwd()
		sys.argv.remove('--wget-url')
		do_then_exit = wget_url

	if '--dont-rest' in sys.argv:
		dont_rest = True
		sys.argv.remove('--dont-rest')
	else:
		dont_rest = False

	if '-h' in sys.argv or '--help' in sys.argv: 
		usage(); exit(0)

	dists = set() # http://mirrors.163.com/ubuntu/dist/jammy/ ...
	packages_gz = set()
	sources_gz = set()

	try: 
		dot_json = parse_json(dists, packages_gz, sources_gz)
		thread = dot_json['thread']
	except Exception as e: print(e);exit(0)

	if dont_rest:
		dot_json['rest'] = [0, 0]
		dot_json['wait'][2] = 0

	# FIXME
	#exit(do_update(thread, dists, packages_gz, sources_gz))

	if do_then_exit: exit(do_then_exit(thread, dists, packages_gz, sources_gz))
	check_default_setting()

	# save jammy-url.ALL
	wd.write_to_file('jammy-urls.ALL', dists)

	if update_index or download_index: down_index(list(dists), thread)

	if download_pool: 
		urls = parse_package(packages_gz, sources_gz, 'content-urls.ALL')
		# 分析日志文件内容，去除已经下载文件
		# 如果本地已经有下载文件了重新检查下载一次
		omit = set()
		cc = 0
		hint=('-','\\','|','/')
		for fn in glob.glob('content-logs.[0-9]*'):
			print(f'\r\033[K<<- {fn}', end='')
			for http in omit_or_saved_from_log(fn):
				omit.add(http)
				cc += 1
				if cc%100==0: print(f'\r\033[K{hint[int(cc/100%4)]} {cc}', end='', flush=True)
			print(f'\r\033[K<<- {fn} {cc}')
		urls -= omit
		if omit: wd.write_to_file('omit.ALL', omit)
		down_pool(list(urls), thread)
		if not miss_check(0, dists, packages_gz, sources_gz):
			do_missing_down(thread)
