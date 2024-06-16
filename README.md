Sun Jun  2 14:50:53 CST 2024
	--parse-package-only ok
	--clean_index removed
	--sanify-check ok

Tue Apr 30 04:19:51 CST 2024
	增加本地废弃文件清理功能。

Fri Mar  8 04:26:16 CST 2024
	增加--continue功能。从上次下载的列表文件开始继续下载。
	分析列表文件与本地已经下载的文件比较去重。重新生成下载列表。
	重新生成下载文件时要分析正在下载的文件，有可能是没有下载完成的。
