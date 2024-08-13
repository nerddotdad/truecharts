#!/bin/bash
#Author itzteajay-glitch

# Function validates all files exist in home directory
function checkHomeDirFiles() {
	echo "INFO: checking home dir for appropriate files"
	cd /home/$USER
	for fileCheck in .bashrc .bash_aliases_clustertool
	do
		declare file_name_$fileCheck:1=${fileCheck}
		echo "INFO: Variable (${!file_name_$fileCheck:1)}
		if [ -e ${fileCheck} ]
			then
				declare file_$fileCheck:1="True"
				echo "INFO: $fileCheck located in home dir - Check Passed"
			else
				declare file_$fileCheck:1="False"
				echo "WARN: $fileCheck was not found - Check Failed"
			fi
	done
}

updateHomeDir() {
	for status in ${!file_bashrc} ${!file_bash_aliases_clustertool}
	do
		if [ ${status} == "False" ]
			then
				
			fi
	done
	
}

checkHomeDir