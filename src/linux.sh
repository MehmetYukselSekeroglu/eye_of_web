#!/usr/bin/env bash
# The EyeOfWeb cli controller version 1.0
# color codes 
red='\033[1;31m'
green='\033[1;32m'
yellow='\033[1;33m'
blue='\033[1;34m'
light_cyan='\033[1;96m'
reset='\033[0m'
#source "/etc/os-release"
# global const varables 
CONFIG_PATH="config/config.json"
DATABASE_SCHEMA_PATH="sql/postgresql_schema.sql"
CONTAINER_SCHEMA_PATH="/postgresql_schema.sql"
GET_TARGET=$1
SCRIPT_VERSION="1.0"
PIP_PACKAGET_FILE="requirements.txt"
API_EXECUTABLE="web_api.py"
PHP_DOC_DIR="php_client/"
# print functions 

p_error(){
    printf "$red[-]$reset $1 \n"
}

p_info(){
    printf "$green[+]$reset $1 \n"
}

# command checker 
check_command(){
    command -v $1 > /dev/null
    if [[ "$?" != "0" ]]; then
        p_error "$1 Not Found, install $1 and try run this script!"
        exit 1
    else
        p_info "$1 detected in system\tOK..."
    
    fi 

}

# check all commands 
check_reqiered_commands(){

    p_info "CHECKING REQUIRED PACKAGETS"
    printf "\n"
    
    check_command "nohup"
    check_command "jq"
    check_command "docker"
    check_command "python3"
    check_command "sudo"
    check_command "cat"
    check_command "make"
    check_command "cmake"
    check_command "gcc"
    check_command "sed"
    printf "\n"

}

# help menu printer 
print_help_exit(){
    printf "\n"
    
    printf "$blue<-[ Help Menu ]->\n$reset"  
    p_info "Script Version:\t$SCRIPT_VERSION"
    printf "\n"

    printf "COMMANDS:\n"
    
    printf "$0 --check-commands\t:Check the required commands status\n"
    printf "$0 --generate-docker\t:Create the docker container for PostgreSQL\n"
    printf "$0 --prepare-psql\t:Create database and execute database schema\n"
    printf "$0 --start-container\t:Start the container\n"
    printf "$0 --stop-container\t:Stop the running container\n"
    printf "$0 --remove-container\t:Remove container and database !DANGER!\n"
    printf "$0 --sql-shell\t\t:Connect PostgreSQL cli on \"$db_name\" database\n"
    printf "$0 --help/-h\t\t:Open this menu\n"
    printf "\n"
    exit 0

}

# reading conf file 
# conf file type    : json 
# bash json parser  : jq
p_info "Reading Config File:\t$CONFIG_PATH"
db_username=postgres
db_password=password
db_hostname="localhost"
db_port="5432"

# parse json data with sed rmove " chars
db_name=$(echo $db_name | sed 's/"//g')
db_username=$(echo $db_username | sed 's/"//g')
db_password=$(echo $db_password | sed 's/"//g')
db_hostname=$(echo $db_hostname | sed 's/"//g')
db_port=$(echo $db_port | sed 's/"//g')

# set container name and max postgreSQL connection 
container_name="static-postgresql-docker"
postgre_max_connections=2000
container_package_name="pgvector/pgvector:pg17"   # container package name


# parse the argumant and execute the protocol 

# handle --generate-docker 
if [[ "$1" == "--generate-docker" ]] ;then
    printf "\n"
    printf "$blue<-[ Starting Docker Generator ]->\n$reset"    

    # call all command checker func 
    check_reqiered_commands

    # user feedback
    p_info "Printing your database config...\n"
    
    printf "[db_name]   -> \t$db_name \n"
    printf "[db_user]   -> \t$db_username \n"
    printf "[db_pass]   -> \t$db_password \n"
    printf "[db_host]   -> \t$db_hostname \n"
    printf "[db_port]   -> \t$db_port\n"
    printf "[max_conn]  -> \t$postgre_max_connections\n"
    printf "[container_name] -> \t$container_name\n"

    printf "\n"
    sleep 1

    # execute main docker command 
    sudo docker run --name $container_name -d -p 5432:$db_port -e POSTGRES_PASSWORD=$db_password $container_package_name -N $postgre_max_connections

    # check command status 
    if [[ "$?" != "0" ]]; then
        p_error "PostgreSQL docker setup failed!"
        exit 1

    else
        p_info "PostgreSQL docker setup successfuly\tOK..."
    
    fi 

    # feedback and exit with code 0
    p_info "Docker generation successfuly !"
    exit 0


# handle --prepare-sql
# create database and execute .sql database schema 

elif [[ "$1" == "--prepare-psql" ]]; then
    printf "\n"
    printf "$blue<-[ Generating PostgreSQL databse and executing schema ]->\n$reset"    

    check_reqiered_commands



    p_info "Printing your database config...\n"
    
    printf "[db_name]   -> \t$db_name \n"
    printf "[db_user]   -> \t$db_username \n"
    printf "[db_pass]   -> \t$db_password \n"
    printf "[db_host]   -> \t$db_hostname \n"
    printf "[db_port]   -> \t$db_port\n"
    printf "[max_conn]  -> \t$postgre_max_connections\n"
    printf "[container_name] -> \t$container_name\n"

    printf "\n"
    sleep 1
    printf "\n"
    p_info "Creating database:\t$db_name"
    sudo docker exec -t $container_name psql -p $db_port -h $db_hostname -U $db_username -c "CREATE DATABASE \"$db_name\";"
    if [[ "$?" != "0" ]]; then
        p_error "Failed to create database: $db_name !"
        exit 1

    else
        p_info "$db_name successfuly created"
    
    fi 
    
    p_info "Copy $DATABASE_SCHEMA_PATH -> $container_name"
    sudo docker cp $DATABASE_SCHEMA_PATH $container_name:$CONTAINER_SCHEMA_PATH
    if [[ "$?" != "0" ]]; then
        p_error "Failed to copy database schema!"
        exit 1

    else
        p_info "OK..."
    
    fi 

    printf "\n"
    p_info "Executing database schema:\t$DATABASE_SCHEMA_PATH"
    sudo docker exec -t $container_name psql -p $db_port -h $db_hostname -U $db_username -d "$db_name" -f $CONTAINER_SCHEMA_PATH
    if [[ "$?" != "0" ]]; then
        p_error "Failed to execute database schema !"
        exit 1

    else
        p_info "Database schema successfuly executed"
    
    fi 
    
    printf "\n"
    p_info "PostgreSQL server is readdy!"
    exit 0



# stop container for user 
elif [[ "$1" == "--stop-container" ]]; then
    printf "\n"
    printf "$blue<-[ Stopping Docker Container ]->\n$reset"  
    printf "\n"
    sleep 1

    sudo docker stop $container_name

    if [[ "$?" != "0" ]]; then
        p_error "Failed to stop docker container:\t$container_name !"
        exit 1

    else
        p_info "OK..."
    
    fi 
    
    printf "\n"
    p_info "Container Successfully stopped:\t$container_name!"
    exit 0

# stop container for user 
elif [[ "$1" == "--start-container" ]]; then
    printf "\n"
    printf "$blue<-[ Starting Docker Container ]->\n$reset"  
    printf "\n"
    sleep 1

    sudo docker start $container_name

    if [[ "$?" != "0" ]]; then
        p_error "Failed to start docker container:\t$container_name !"
        exit 1

    else
        p_info "OK..."
    
    fi 
    
    printf "\n"
    p_info "Container Successfully start:\t$container_name!"
    exit 0

# romove/delete container 
# for uninstall or reinstall
elif [[ "$1" == "--remove-container" ]]; then
    printf "\n"
    printf "$blue<-[ Removing Docker Container ]->\n$reset"  
    printf "\n"
    sleep 1

    p_info "Stopping container..."
    sudo docker stop $container_name
    if [[ "$?" != "0" ]]; then
        p_error "Failed to stop docker container:\t$container_name !"
        exit 1

    else
        p_info "OK..."
    
    fi 
    
    p_info "Removing container..."
    sudo docker rm $container_name
    if [[ "$?" != "0" ]]; then
        p_error "Failed to delete docker container:\t$container_name !"
        exit 1

    else
        p_info "OK..."
    
    fi 
    

    printf "\n"
    p_info "Container Successfully removed:\t$container_name!"
    exit 0


# quick sql shell with psql
elif [[ "$1" == "--sql-shell" ]]; then
    printf "\n"
    printf "$blue<-[ Starting SQL shell on PostgreSQL container ]->\n$reset"  
    printf "\n"
    sudo docker exec -it $container_name psql -p $db_port -h $db_hostname -U $db_username -d "$db_name" 
    p_info "OK.."
    exit 0


elif [[ "$1" == "--install-pip-packagets" ]]; then
    printf "\n"
    printf "$blue<-[ Starting pip package installing ]->\n$reset"  
    printf "\n"
    sleep 1

    p_info "Using file:\t$PIP_PACKAGET_FILE"

    python3 -m pip install -r $PIP_PACKAGET_FILE 2> /dev/null



    exit 0
    

#! start all service not finished !!
elif [[ "$1" == "--saasd" ]]; then
    printf "\n"
    printf "$blue<-[ Starting Api And Php Client ]->\n$reset"  
    printf "\n"
    
    network_status=$(cat $CONFIG_PATH | jq ".api_config.localhost_only")

    if [[ "$network_status" == "false" ]] ;then
        php_command="php -S 0.0.0.0:8080 > php.log &"
        api_command="python3 web_api.py > api.log &"
        p_info "Executing: $php_command"
        p_info "Executing: $api_command"

        $(echo $php_command)
        $(echo $api_command)

        $( ps -aux | grep -i $php_command)
        $( ps -aux | grep -i $web_api)

    fi



    sleep 1
    exit 0

# manuel command check for user 
elif [[ "$1" == "--check-commands" ]]; then
    check_reqiered_commands

# handle --help 
elif [[ "$1" == "--help" || "$1" == "-h" ]]; then
    print_help_exit
    

# invalid arg handler 
else

    p_error "Invalid args!"
    print_help_exit

fi
