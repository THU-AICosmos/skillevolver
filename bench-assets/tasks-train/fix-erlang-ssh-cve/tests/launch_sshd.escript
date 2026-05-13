#!/usr/bin/env escript
%%! -sname sshd_node

main(_) ->
    application:start(asn1),
    application:start(crypto),
    application:start(public_key),
    application:start(ssh),

    io:format("Launching Erlang SSH daemon on port 3333...~n"),

    case ssh:daemon(3333, [
        {system_dir, "/etc/ssh"},

        {user_dir_fun, fun(User) ->
            Home = filename:join("/home", User),
            io:format("Resolving SSH dir for ~p: ~s/.ssh~n", [User, Home]),
            filename:join(Home, ".ssh")
        end},

        {connectfun, fun(User, Peer, AuthMethod) ->
            io:format("Authenticated: user=~p peer=~p method=~p~n",
                      [User, Peer, AuthMethod]),
            true
        end},

        {failfun, fun(User, Peer, Why) ->
            io:format("Auth rejected: user=~p peer=~p reason=~p~n",
                      [User, Peer, Why]),
            true
        end},

        {auth_methods, "publickey,password"},

        {user_passwords, [{"admin", "s3cure_pass"}]},
        {idle_time, infinity},
        {max_channels, 10},
        {max_sessions, 10},
        {parallel_login, true}
    ]) of
        {ok, _Pid} ->
            io:format("SSH daemon active on port 3333. Waiting indefinitely...~n");
        {error, Reason} ->
            io:format("SSH daemon failed to start: ~p~n", [Reason])
    end,

    receive
        halt -> ok
    end.
