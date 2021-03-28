                    <div id="boardcontents_placeholder">
                    <div class="row">
                    <!-- this place will show the actual contents of the blackboard. 
                    It will be reloaded automatically from the server -->
                        <div class="card shadow mb-4 w-100">
                            <div class="card-header py-3">
                                <h6 class="font-weight-bold text-primary">Blackboard content</h6>
                            </div>
                            <div class="card-body">
                                <input type="text" name="id" value="ID" readonly>
                                <input type="text" name="entry" value="Clock" readonly>
                                <input type="text" name="entry" value="Entry" size="40%%" readonly>
                                % for key in sorted(board_dict.keys()):
                                    <form class="entryform" target="noreload-form-target" method="post" action="/board/{{key}}/">
                                        <input type="text" name="id" value="{{key}}" readonly disabled> <!-- disabled field won’t be sent -->
                                        
                                        <input type="text" name="clock" value="{{board_dict[key]["clock"]}}" readonly disabled>
                                        <input type="text" name="entry" value="{{board_dict[key]["entry"]}}" size="40%%">
                                        <input type="hidden" name="creator_ip" value="{{board_dict[key]["creator_ip"]}}">
                                        
                                        <input type="hidden" name="seq" value="{{key}}">
                                        <button type="submit" name="delete" value="0">Modify</button>
                                        <button type="submit" name="delete" value="1">X</button>
                                    </form>
                                %end
                            </div>
                        </div>
                    </div>
                    </div>
