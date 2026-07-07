--[[
DeSmuME connector for Archipelago's generic BizHawk client.

This script makes DeSmuME speak the exact same TCP/JSON protocol as
`connector_bizhawk_generic.lua`, so Archipelago's existing `_bizhawk`
client (used by the Pokemon HeartGold/SoulSilver world, among others)
can talk to DeSmuME without any changes on the client side. It gives
macOS/Linux users an alternative to BizHawk.

--------------------------------------------------------------------------
REQUIREMENTS
--------------------------------------------------------------------------
DeSmuME's Lua runtime (Lua 5.1) does not bundle LuaSocket, and this
protocol needs a TCP server, so you must have LuaSocket available to
DeSmuME's interpreter. The Lua 5.1 C ABI is stable, so a system LuaSocket
built for 5.1 works.

macOS:
    brew install lua@5.1 luarocks
    luarocks --lua-version=5.1 install luasocket
    # then note where socket/core.so and mime/core.so were installed, e.g.
    #   ~/.luarocks/lib/lua/5.1/  or  /opt/homebrew/lib/lua/5.1/

If `require("socket")` fails, set these environment variables before
launching DeSmuME (adjust the paths to your install):
    export LUA_CPATH="/opt/homebrew/lib/lua/5.1/?.so;;"
    export LUA_PATH="/opt/homebrew/share/lua/5.1/?.lua;;"

--------------------------------------------------------------------------
USAGE
--------------------------------------------------------------------------
1. Load your patched ROM in DeSmuME and let it run past the title screen.
2. Open Tools -> Lua Script Console (or the "New Lua Script Window"),
   browse to this file, and Run it.
3. Start the Archipelago client (e.g. the Pokemon Client / BizHawk Client
   launcher entry). It will connect to this script automatically.

--------------------------------------------------------------------------
MEMORY DOMAINS
--------------------------------------------------------------------------
BizHawk exposes named memory "domains"; DeSmuME has a single flat ARM9
address space. Domains are mapped as follows:

    "ARM9 System Bus" / "System Bus"  -> ARM9 bus, address used as-is
    "Main RAM"                        -> ARM9 bus, address + 0x02000000
    "ROM"                             -> cart header copy in main RAM at
                                         0x027FFE00 (covers the header /
                                         game-title reads AP clients use
                                         to identify the ROM)

Only ARM9-visible memory is reachable from DeSmuME Lua, so an "ARM7
System Bus" domain is not supported and will return an ERROR.
]]

local SCRIPT_VERSION = 1

-- Set to true to log every incoming request (very noisy / laggy).
local DEBUG = false

--------------------------------------------------------------------------
-- LuaSocket
--------------------------------------------------------------------------

local ok_socket, socket = pcall(require, "socket")
if not ok_socket then
    print("ERROR: could not load LuaSocket (require(\"socket\") failed).")
    print(tostring(socket))
    print("")
    print("DeSmuME's Lua needs LuaSocket (Lua 5.1) for this connector.")
    print("Install it and point LUA_CPATH/LUA_PATH at it, e.g. on macOS:")
    print("  brew install lua@5.1 luarocks")
    print("  luarocks --lua-version=5.1 install luasocket")
    print("  export LUA_CPATH=\"/opt/homebrew/lib/lua/5.1/?.so;;\"")
    print("See the comment block at the top of this script for details.")
    return
end

--------------------------------------------------------------------------
-- base64 (byte-array <-> string), matching the BizHawk connector's
-- base64 lib semantics: decode returns a 1-based array of byte ints,
-- encode accepts a 1-based array of byte ints.
--------------------------------------------------------------------------

local B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
local B64_LOOKUP = {}
for i = 1, #B64 do
    B64_LOOKUP[B64:sub(i, i)] = i - 1
end

local function base64_encode(arr)
    local out = {}
    local n = #arr
    local i = 1
    while i <= n do
        local b1 = arr[i]
        local b2 = arr[i + 1]
        local b3 = arr[i + 2]

        local n1 = math.floor(b1 / 4)
        local n2 = (b1 % 4) * 16 + math.floor((b2 or 0) / 16)
        local n3 = ((b2 or 0) % 16) * 4 + math.floor((b3 or 0) / 64)
        local n4 = (b3 or 0) % 64

        out[#out + 1] = B64:sub(n1 + 1, n1 + 1)
        out[#out + 1] = B64:sub(n2 + 1, n2 + 1)
        out[#out + 1] = (b2 == nil) and "=" or B64:sub(n3 + 1, n3 + 1)
        out[#out + 1] = (b3 == nil) and "=" or B64:sub(n4 + 1, n4 + 1)

        i = i + 3
    end
    return table.concat(out)
end

local function base64_decode(str)
    local out = {}
    local buffer = 0
    local bits = 0
    for c in str:gmatch(".") do
        if c == "=" then break end
        local v = B64_LOOKUP[c]
        if v ~= nil then
            buffer = buffer * 64 + v
            bits = bits + 6
            if bits >= 8 then
                bits = bits - 8
                local divisor = 2 ^ bits
                out[#out + 1] = math.floor(buffer / divisor) % 256
                buffer = buffer % divisor
            end
        end
    end
    return out
end

--------------------------------------------------------------------------
-- Minimal JSON encode/decode (sufficient for this protocol).
--------------------------------------------------------------------------

local ESCAPE_MAP = {
    ['"'] = '\\"', ["\\"] = "\\\\", ["\n"] = "\\n", ["\r"] = "\\r",
    ["\t"] = "\\t", ["\b"] = "\\b", ["\f"] = "\\f",
}

local function json_encode_string(s)
    local escaped = s:gsub('[%z\1-\31\\"]', function(c)
        return ESCAPE_MAP[c] or string.format("\\u%04x", string.byte(c))
    end)
    return '"' .. escaped .. '"'
end

local function is_array(t)
    local n = 0
    for k in pairs(t) do
        if type(k) ~= "number" then return false end
        n = n + 1
    end
    for i = 1, n do
        if t[i] == nil then return false end
    end
    return n > 0
end

local json_encode
json_encode = function(v)
    local t = type(v)
    if v == nil then
        return "null"
    elseif t == "boolean" then
        return v and "true" or "false"
    elseif t == "number" then
        if v == math.floor(v) and math.abs(v) < 2 ^ 53 then
            return string.format("%d", v)
        end
        return tostring(v)
    elseif t == "string" then
        return json_encode_string(v)
    elseif t == "table" then
        local parts = {}
        if is_array(v) then
            for i = 1, #v do
                parts[i] = json_encode(v[i])
            end
            return "[" .. table.concat(parts, ",") .. "]"
        end
        for k, val in pairs(v) do
            parts[#parts + 1] = json_encode_string(tostring(k)) .. ":" .. json_encode(val)
        end
        return "{" .. table.concat(parts, ",") .. "}"
    end
    error("cannot encode value of type " .. t)
end

local function json_decode(str)
    local pos = 1
    local parse_value

    local function skip_ws()
        local _, e = str:find("^[ \t\r\n]+", pos)
        if e then pos = e + 1 end
    end

    local function parse_string()
        pos = pos + 1 -- skip opening quote
        local buf = {}
        while true do
            local c = str:sub(pos, pos)
            if c == "" then error("unterminated string") end
            if c == '"' then
                pos = pos + 1
                break
            elseif c == "\\" then
                local e = str:sub(pos + 1, pos + 1)
                if e == "n" then buf[#buf + 1] = "\n"
                elseif e == "t" then buf[#buf + 1] = "\t"
                elseif e == "r" then buf[#buf + 1] = "\r"
                elseif e == "b" then buf[#buf + 1] = "\b"
                elseif e == "f" then buf[#buf + 1] = "\f"
                elseif e == "/" then buf[#buf + 1] = "/"
                elseif e == "\\" then buf[#buf + 1] = "\\"
                elseif e == '"' then buf[#buf + 1] = '"'
                elseif e == "u" then
                    local code = tonumber(str:sub(pos + 2, pos + 5), 16) or 0
                    if code < 0x80 then
                        buf[#buf + 1] = string.char(code)
                    elseif code < 0x800 then
                        buf[#buf + 1] = string.char(0xC0 + math.floor(code / 0x40),
                                                    0x80 + (code % 0x40))
                    else
                        buf[#buf + 1] = string.char(0xE0 + math.floor(code / 0x1000),
                                                    0x80 + (math.floor(code / 0x40) % 0x40),
                                                    0x80 + (code % 0x40))
                    end
                    pos = pos + 4
                else
                    buf[#buf + 1] = e
                end
                pos = pos + 2
            else
                buf[#buf + 1] = c
                pos = pos + 1
            end
        end
        return table.concat(buf)
    end

    local function parse_number()
        local s, e = str:find("^%-?%d+%.?%d*[eE]?[%+%-]?%d*", pos)
        local numstr = str:sub(s, e)
        pos = e + 1
        return tonumber(numstr)
    end

    local function parse_object()
        pos = pos + 1 -- skip {
        local obj = {}
        skip_ws()
        if str:sub(pos, pos) == "}" then
            pos = pos + 1
            return obj
        end
        while true do
            skip_ws()
            local key = parse_string()
            skip_ws()
            pos = pos + 1 -- skip :
            obj[key] = parse_value()
            skip_ws()
            local ch = str:sub(pos, pos)
            pos = pos + 1
            if ch == "}" then break end
            if ch ~= "," then error("expected ',' or '}' in object") end
        end
        return obj
    end

    local function parse_array()
        pos = pos + 1 -- skip [
        local arr = {}
        skip_ws()
        if str:sub(pos, pos) == "]" then
            pos = pos + 1
            return arr
        end
        while true do
            arr[#arr + 1] = parse_value()
            skip_ws()
            local ch = str:sub(pos, pos)
            pos = pos + 1
            if ch == "]" then break end
            if ch ~= "," then error("expected ',' or ']' in array") end
        end
        return arr
    end

    parse_value = function()
        skip_ws()
        local c = str:sub(pos, pos)
        if c == "{" then return parse_object()
        elseif c == "[" then return parse_array()
        elseif c == '"' then return parse_string()
        elseif c == "t" then pos = pos + 4 return true
        elseif c == "f" then pos = pos + 5 return false
        elseif c == "n" then pos = pos + 4 return nil
        else return parse_number() end
    end

    return parse_value()
end

--------------------------------------------------------------------------
-- Memory domain mapping (BizHawk domain name -> ARM9 bus base address)
--------------------------------------------------------------------------

local DOMAIN_BASE = {
    ["ARM9 System Bus"] = 0x00000000,
    ["System Bus"] = 0x00000000,
    ["Main RAM"] = 0x02000000,
    ["ROM"] = 0x027FFE00, -- cart header copy in main RAM
}

local DOMAIN_SIZE = {
    ["ARM9 System Bus"] = 0x10000000,
    ["System Bus"] = 0x10000000,
    ["Main RAM"] = 0x00400000,
    ["ROM"] = 0x00000160, -- just the header region we can serve
}

local function resolve_address(domain, address)
    local base = DOMAIN_BASE[domain]
    if base == nil then
        error("Unsupported memory domain: " .. tostring(domain))
    end
    return base + address
end

local function read_bytes(domain, address, size)
    local start = resolve_address(domain, address)
    local raw = memory.readbyterange(start, size)
    -- readbyterange leaves invalid addresses nil; normalize to 0.
    local out = {}
    for i = 1, size do
        out[i] = raw[i] or 0
    end
    return out
end

local function write_bytes(domain, address, bytes)
    if domain == "ROM" then
        error("Cannot write to ROM domain")
    end
    local start = resolve_address(domain, address)
    for i = 1, #bytes do
        memory.writebyte(start + (i - 1), bytes[i])
    end
end

--------------------------------------------------------------------------
-- ROM identity / hash (stable per loaded ROM, used to detect ROM swaps)
--------------------------------------------------------------------------

local function compute_rom_hash()
    -- Header title (0x00, 12 bytes) + game code (0x0C, 4 bytes) from the
    -- cart header copy in main RAM, hex-encoded. Stable for a given ROM.
    local bytes = read_bytes("ROM", 0, 16)
    local parts = {}
    for i = 1, #bytes do
        parts[i] = string.format("%02X", bytes[i])
    end
    return table.concat(parts)
end

--------------------------------------------------------------------------
-- Request handlers (mirror connector_bizhawk_generic.lua)
--------------------------------------------------------------------------

local rom_hash = nil
local message_queue = {}
local message_interval = 0
local message_timer = 0

local locked = false
local client_socket = nil

local function lock()
    locked = true
    if client_socket then client_socket:settimeout(2) end
end

local function unlock()
    locked = false
    if client_socket then client_socket:settimeout(0) end
end

local request_handlers = {
    ["PING"] = function()
        return { type = "PONG" }
    end,

    ["SYSTEM"] = function()
        return { type = "SYSTEM_RESPONSE", value = "NDS" }
    end,

    ["PREFERRED_CORES"] = function()
        -- NDS has a single core in DeSmuME; nothing meaningful to report.
        return { type = "PREFERRED_CORES_RESPONSE", value = {} }
    end,

    ["HASH"] = function()
        return { type = "HASH_RESPONSE", value = rom_hash }
    end,

    ["MEMORY_SIZE"] = function(req)
        return { type = "MEMORY_SIZE_RESPONSE", value = DOMAIN_SIZE[req["domain"]] or 0 }
    end,

    ["GUARD"] = function(req)
        local expected = base64_decode(req["expected_data"])
        local actual = read_bytes(req["domain"], req["address"], #expected)
        local validated = true
        for i = 1, #expected do
            if actual[i] ~= expected[i] then
                validated = false
                break
            end
        end
        return { type = "GUARD_RESPONSE", value = validated, address = req["address"] }
    end,

    ["LOCK"] = function()
        lock()
        return { type = "LOCKED" }
    end,

    ["UNLOCK"] = function()
        unlock()
        return { type = "UNLOCKED" }
    end,

    ["READ"] = function(req)
        local bytes = read_bytes(req["domain"], req["address"], req["size"])
        return { type = "READ_RESPONSE", value = base64_encode(bytes) }
    end,

    ["WRITE"] = function(req)
        write_bytes(req["domain"], req["address"], base64_decode(req["value"]))
        return { type = "WRITE_RESPONSE" }
    end,

    ["DISPLAY_MESSAGE"] = function(req)
        message_queue[#message_queue + 1] = req["message"]
        return { type = "DISPLAY_MESSAGE_RESPONSE" }
    end,

    ["SET_MESSAGE_INTERVAL"] = function(req)
        message_interval = req["value"]
        return { type = "SET_MESSAGE_INTERVAL_RESPONSE" }
    end,
}

local function process_request(req)
    local handler = request_handlers[req["type"]]
    if handler then
        return handler(req)
    end
    return { type = "ERROR", err = "Unknown command: " .. tostring(req["type"]) }
end

--------------------------------------------------------------------------
-- Networking
--------------------------------------------------------------------------

local SOCKET_PORT_FIRST = 43055
local SOCKET_PORT_LAST = SOCKET_PORT_FIRST + 5

local STATE_NOT_CONNECTED = 0
local STATE_CONNECTED = 1

local server = nil
local current_state = STATE_NOT_CONNECTED

local recv_buffer = ""
local timeout_timer = 0
local prev_time = socket.gettime()

local function initialize_server()
    local port = SOCKET_PORT_FIRST
    while port <= SOCKET_PORT_LAST do
        local srv, err = socket.bind("localhost", port)
        if srv then
            srv:settimeout(0)
            server = srv
            print("DeSmuME AP connector listening on localhost:" .. port)
            return
        elseif err ~= "address already in use" and err ~= nil then
            -- Some LuaSocket builds report the busy-port differently; only
            -- bail on genuinely unexpected errors.
            if not tostring(err):find("in use") and not tostring(err):find("bind") then
                print("Socket error: " .. tostring(err))
                return
            end
        end
        port = port + 1
    end
    print("Too many instances of the connector already running. Exiting.")
end

-- Pull one complete '\n'-terminated line from the socket, buffering
-- partial reads across frames. Returns line, err.
local function receive_line()
    local chunk, err, partial = client_socket:receive("*l")
    if chunk then
        local line = recv_buffer .. chunk
        recv_buffer = ""
        return line, nil
    end
    if partial and #partial > 0 then
        recv_buffer = recv_buffer .. partial
    end
    return nil, err
end

local function send_receive()
    local message, err = receive_line()

    if err == "closed" then
        if current_state == STATE_CONNECTED then
            print("Connection to client closed")
        end
        current_state = STATE_NOT_CONNECTED
        return
    elseif err == "timeout" then
        unlock()
        return
    elseif err ~= nil then
        print(tostring(err))
        current_state = STATE_NOT_CONNECTED
        unlock()
        return
    end

    if message == nil then
        return
    end

    timeout_timer = 5

    if DEBUG then
        print("Received [" .. emu.framecount() .. "]: " .. message)
    end

    if message == "VERSION" then
        client_socket:send(tostring(SCRIPT_VERSION) .. "\n")
        return
    end

    local res = {}
    local data = json_decode(message)
    local failed_guard = nil
    for i, req in ipairs(data) do
        if failed_guard ~= nil then
            res[i] = failed_guard
        else
            local status, response = pcall(process_request, req)
            if status then
                res[i] = response
                if response["type"] == "GUARD_RESPONSE" and not response["value"] then
                    failed_guard = response
                end
            else
                if type(response) ~= "string" then response = "Unknown error" end
                res[i] = { type = "ERROR", err = response }
            end
        end
    end

    client_socket:send(json_encode(res) .. "\n")
end

--------------------------------------------------------------------------
-- Main per-frame tick
--------------------------------------------------------------------------

local function tick()
    if server == nil and current_state == STATE_NOT_CONNECTED then
        initialize_server()
        if server == nil then return end
    end

    local now = socket.gettime()
    local dt = now - prev_time
    prev_time = now
    timeout_timer = timeout_timer - dt
    message_timer = message_timer - dt

    if message_timer <= 0 and #message_queue > 0 then
        emu.message(table.remove(message_queue, 1))
        message_timer = message_interval
    end

    if current_state == STATE_NOT_CONNECTED then
        recv_buffer = ""
        if emu.framecount() % 30 == 0 and server ~= nil then
            local client = server:accept()
            if client then
                print("Client connected")
                current_state = STATE_CONNECTED
                client_socket = client
                client_socket:settimeout(0)
                timeout_timer = 5
            end
        end
    else
        repeat
            send_receive()
        until not locked or current_state == STATE_NOT_CONNECTED

        if timeout_timer <= 0 then
            print("Client timed out")
            current_state = STATE_NOT_CONNECTED
            client_socket = nil
        end
    end
end

--------------------------------------------------------------------------
-- Startup
--------------------------------------------------------------------------

emu.registerexit(function()
    print("\n-- DeSmuME AP connector stopping --\n")
    if client_socket then client_socket:close() end
    if server then server:close() end
end)

rom_hash = compute_rom_hash()
print("DeSmuME Archipelago connector v" .. SCRIPT_VERSION .. " started.")
print("Waiting for the Archipelago client to connect...")

while true do
    -- Guard the whole tick so a transient error doesn't kill the loop.
    local status, err = pcall(tick)
    if not status then
        print("Connector error: " .. tostring(err))
    end
    emu.frameadvance()
end
