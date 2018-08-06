#!/bin/bash
echo '<HTML><HEAD><TITLE>my_webserver</TITLE></HEAD><BODY>'; 
echo "<b><u> $(ps -p $(ps aux | grep test.py |grep -v grep |awk {'print $2'}) -o  pcpu,pmem) </u></b><BR>"; 
echo '</BODY></HTML>';
