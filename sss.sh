#!/bin/bash
echo '<HTML><HEAD><TITLE>my_webserver</TITLE></HEAD><BODY>'; 
echo "<b><u> $(uptime|awk {'print $6" "$7" "$8" "$9" "$10'})</u></b><BR>"; 
echo "Memory usage: $(free -mh|head -n2)";
echo "commit ID: $(cd /my_volume/my_git; git log > file;head -n 1 file | awk '{print $2}'; rm -f file;)";
echo '</BODY></HTML>';
