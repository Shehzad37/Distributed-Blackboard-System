# coding=utf-8
import argparse
import json
import sys
from threading import Lock, Thread
import time
import traceback
import bottle
from bottle import Bottle, request, template, run, static_file
import requests
from multiprocessing.dummy import Pool as ThreadPool
# ------------------------------------------------------------------------------------------------------

class Blackboard():

    def __init__(self):
        self.content = ""
        self.lock = Lock() # use lock when you modify the content
        self.contentObj = dict()


    def get_content(self):
        with self.lock:
            cnt = self.contentObj
        return cnt

    def set_content(self, new_content, id):
        with self.lock:
            self.contentObj[id] = new_content
        return


# ------------------------------------------------------------------------------------------------------
class Server(Bottle):

    def __init__(self, ID, IP, servers_list):
        super(Server, self).__init__()
        self.blackboard = Blackboard()
        self.id = int(ID)
        self.ip = str(IP)
        self.servers_list = servers_list
        self.lock = Lock()  # use lock when you modify the giveAccessFlag for queue
        self.logicalClock = 0
        self.network_fail_data = dict()

        # list all REST URIs
        # if you add new URIs to the server, you need to add them here
        self.route('/', callback=self.index)
        self.get('/board', callback=self.get_board)
        self.post('/board', callback=self.post_board)
        self.post('/receivedMessage', callback=self.receivedMessage)
        self.post('/board/<element_id:int>/',callback=self.del_edit_board)
        # we give access to the templates elements
        self.get('/templates/<filename:path>', callback=self.get_template)
        # You can have variables in the URI, here's an example
        # self.post('/board/<element_id:int>/', callback=self.post_board) where post_board takes an argument (integer) called element_id


    def do_parallel_task(self, method, args=None):
        # create a thread running a new task
        # Usage example: self.do_parallel_task(self.contact_another_server, args=("10.1.0.2", "/index", "POST", params_dict))
        # this would start a thread sending a post request to server 10.1.0.2 with URI /index and with params params_dict
        thread = Thread(target=method,
                        args=args)
        thread.daemon = True
        thread.start()



    def do_parallel_task_after_delay(self, delay, method, args=None):
        # create a thread, and run a task after a specified delay
        # Usage example: self.do_parallel_task_after_delay(10, self.start_election, args=(,))
        # this would start a thread starting an election after 10 seconds
        thread = Thread(target=self._wrapper_delay_and_execute,
                        args=(delay, method, args))
        thread.daemon = True
        thread.start()


    def _wrapper_delay_and_execute(self, delay, method, args):
        time.sleep(delay) # in sec
        method(*args)


    def contact_another_server(self, srv_ip, URI, req='POST', params_dict=None):
        # Try to contact another serverthrough a POST or GET
        # usage: server.contact_another_server("10.1.1.1", "/index", "POST", params_dict)
        success = False
        try:
            if 'POST' in req:
                res = requests.post('http://{}{}'.format(srv_ip, URI),
                                    data=params_dict)
            elif 'GET' in req:
                res = requests.get('http://{}{}'.format(srv_ip, URI))
            # result can be accessed res.json()
            if res.status_code == 200:
                success = True
        except Exception as e:
                #print("[ERROR In contact Another Server] For data: ", params_dict["entry"], "For IP: ",srv_ip)
                data = {"data": params_dict, "sender_ip" : srv_ip, "uri" : URI}
                self.network_fail_data[params_dict["seq"]] = data

        return success


    def propagate_to_all_servers(self, URI, req='POST', params_dict=None):
        for srv_ip in self.servers_list:
            if srv_ip != self.ip: # don't propagate to yourself
                try:
                    self.do_parallel_task(self.contact_another_server, args=(srv_ip, URI, req, params_dict))                    
                except Exception as e:
                    #print("[Error : In propagate_to_all_servers]")
                    data = {"data": params_dict, "sender_ip" : srv_ip, "uri" : URI}
                    self.network_fail_data[params_dict["seq"]] = data
                    


    def propagate_network_fail_data_to_all_servers(self):
        #Check for any pending data which was failed to send to other server
        if bool(self.network_fail_data):
            temp_data = self.network_fail_data
            for key in temp_data.keys():
                
                if self.network_fail_data[key]["sender_ip"] != self.ip: # don't propagate to yourself
                    success = self.contact_another_server(self.network_fail_data[key]["sender_ip"], self.network_fail_data[key]["uri"], "POST", self.network_fail_data[key]["data"])
                    del self.network_fail_data[key]  
         
        #Call the same method after 20 sec continue is process so that all pending messages can be sent
        self.do_parallel_task_after_delay(40, self.propagate_network_fail_data_to_all_servers, args=())
                    


    # route to ('/')
    def index(self):
        # we must transform the blackboard as a dict for compatiobility reasons
        board = dict()
        board = self.blackboard.get_content()
        return template('server/templates/index.tpl',
                        board_title='Server {} ({})'.format(self.id,
                                                            self.ip),
                        board_dict=board,
                        members_name_string='Shehzad Abbas, Sheraz Tariq')

    # get on ('/board')
    def get_board(self):
        
        # we must transform the blackboard as a dict for compatibility reasons
        board = dict()
        board = self.blackboard.get_content()
        return template('server/templates/blackboard.tpl',
                        board_title='Server {} ({})'.format(self.id,
                                                            self.ip),
                        board_dict=board)


    # post on ('/board')
    def post_board(self):
        try:
            # we read the POST form, and check for an element called 'entry'
            new_entry = request.forms.get('entry')
            self.do_parallel_task(self.sendMessage, args=(new_entry, "add"))
        except Exception as e:
            print("[ERROR in Post Board] "+str(e))


    def get_template(self, filename):
        return static_file(filename, root='./server/templates/')
        

    def get_clock(self):
        with self.lock:
            logicalClock = self.logicalClock
        return logicalClock

    def set_clock(self, logicalClock):
        with self.lock:
            self.logicalClock = logicalClock
        return


    def add_entry(self, entry, seq):
        
        #Add new entry
        self.do_parallel_task(self.blackboard.set_content, args=(entry, int(seq)))
        #self.blackboard.set_content(entry, int(seq))

    def edit_entry(self, entry, element_id):
        
        #Get all the entries
        board = self.blackboard.get_content()
        #Edit the entry
        board[int(element_id)] = entry

    def delete_entry(self, element_id):
        
        #Get all the entries
        board = self.blackboard.get_content()
        #Delete entry
        del board[int(element_id)]
    
    def sendMessage(self, new_entry, action, element_id=0, creator_ip=None, seq=None ):
        try:
            
            #increament local clock before send 
            localClock = self.get_clock() + 1
            self.set_clock(localClock)


            if action == 'add':
                                
                seq = str(localClock)+""+ str(self.ip.replace(".", ""))  
                 
                data = {"action": action, "entry": new_entry, "clock": str(localClock), "creator_ip": self.ip, "seq" : str(seq)}

                #Add new entry locally

                self.do_parallel_task(self.add_entry, args=(data, int(seq) ))
                
                #Send to all other servers 
                self.do_parallel_task(self.propagate_to_all_servers, args=('/receivedMessage', 'POST', data))
                

            if action == 'edit':
                
                
                #Edit entry locally
                localdata = {"entry": new_entry, "creator_ip": creator_ip, "clock": str(localClock), "seq" : str(seq) }
                self.do_parallel_task(self.edit_entry, args=(localdata, element_id ))
                
                #Send to all other servers                
                data = {"action": action, "entry": new_entry, "clock": localClock, "creator_ip": creator_ip, "seq" : element_id}
                self.propagate_to_all_servers('/receivedMessage', 'POST', data)

            if action == 'delete':
                
                #increament local clock before send 
                localClock = self.get_clock() + 1
                self.set_clock(localClock)
                
                #Delete entry locally
                self.delete_entry(element_id)
                
                #Send to all other servers                
                data = {"action": action, "clock": localClock, "creator_ip": self.ip, "seq" : element_id}
                self.propagate_to_all_servers('/receivedMessage', 'POST', data)

        except Exception as e:

            print ('[ERROR in Send Message] ' + str(e))

    def receivedMessage(self):
        try:
            
            action = request.forms.get('action')
            clock = request.forms.get('clock')
            seq = request.forms.get('seq')
            
            #Increament the local clock when message is received
            localClock = max( self.get_clock() , int(clock) ) + 1
            self.set_clock (localClock)            
            #print("Receive Message Type:")
            #print(type(localClock))
            
            if action == 'add':
                
                new_entry = request.forms.get('entry')
                creator_ip = request.forms.get('creator_ip')
                
                data = {"entry": new_entry, "creator_ip": creator_ip, "clock":localClock }
                #Add new entry locally
                #self.add_entry(data, int(seq))
                self.do_parallel_task(self.add_entry, args=(data, int(seq) ))
                
            if action == 'edit':
                
                new_entry = request.forms.get('entry')
                element_id = request.forms.get('seq')
                creator_ip = request.forms.get('creator_ip')

                #Edit entry locally
                data = {"entry": new_entry, "creator_ip": creator_ip, "clock":localClock }
                self.do_parallel_task(self.edit_entry, args=(data, element_id ))

            if action == 'delete':

                element_id = request.forms.get('seq')

                #Delete entry locally
                self.delete_entry(element_id)

        except Exception as e:

            print ('[ERROR in Receive Message] ' + str(e))

    def del_edit_board(self, element_id):
        try:

            new_entry = request.forms.get('entry')
            action = request.forms.get('delete')

            if action == '0':
                creator_ip = request.forms.get('creator_ip')
                seq = request.forms.get('seq')
                self.do_parallel_task(self.sendMessage, args=(new_entry, "edit", element_id, seq ))


            elif action == '1':

                self.do_parallel_task(self.sendMessage, args=(None, "delete", element_id))

        except Exception as e:

            print ('[ERROR] ' + str(e))
# ------------------------------------------------------------------------------------------------------
def main():
    PORT = 80
    parser = argparse.ArgumentParser(description='Your own implementation of the distributed blackboard')
    parser.add_argument('--id',
                        nargs='?',
                        dest='id',
                        default=1,
                        type=int,
                        help='This server ID')
    parser.add_argument('--servers',
                        nargs='?',
                        dest='srv_list',
                        default="10.1.0.1,10.1.0.2",
                        help='List of all servers present in the network')
    args = parser.parse_args()
    server_id = args.id
    server_ip = "10.1.0.{}".format(server_id)
    servers_list = args.srv_list.split(",")

    try:
        server = Server(server_id,
                        server_ip,
                        servers_list)
        server.do_parallel_task(server.propagate_network_fail_data_to_all_servers, args=())

        bottle.run(server,
                   host=server_ip,
                   port=PORT)
        
       
        
    except Exception as e:
        print("[ERROR] "+str(e))


# ------------------------------------------------------------------------------------------------------
if __name__ == '__main__':
    main()
