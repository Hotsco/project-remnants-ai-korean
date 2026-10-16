-- Read-only observations for the local adapter. No game/character state is changed.
NPCFW_LunaContext = NPCFW_LunaContext or {}
local C = NPCFW_LunaContext
C.records = C.records or {}
C.filename = "NPCFW_LunaContext.json"

local function safely(fn)
    local ok, value = pcall(fn)
    if ok then return value, true end
    return nil, false
end
local function call(obj, method)
    return safely(function() return obj[method](obj) end)
end
local function finite(value)
    return type(value)=="number" and value==value and math.abs(value)<10000000000000000
end
local function clean(text)
    return tostring(text or ""):gsub("[%c]", " "):gsub("%s+", " "):match("^%s*(.-)%s*$")
end
local function name(actor)
    local desc = call(actor,"getDescriptor")
    if desc then
        local full = clean(tostring(call(desc,"getForename") or "").." "..tostring(call(desc,"getSurname") or ""))
        if full~="" then return full end
    end
    return clean(call(actor,"getUsername"))
end
local function quote(value)
    return '"'..tostring(value):gsub('[%z\1-\31\\"]',function(c)
        if c=='"' then return '\\"' end
        if c=='\\' then return '\\\\' end
        return string.format('\\u%04x',string.byte(c))
    end)..'"'
end
local function object(values)
    local rows={}
    for key,value in pairs(values) do
        local encoded
        if type(value)=="string" then encoded=quote(value)
        elseif type(value)=="boolean" then encoded=tostring(value)
        elseif finite(value) then encoded=string.format("%.0f",value) end
        if encoded then rows[#rows+1]=quote(key)..":"..encoded end
    end
    table.sort(rows)
    return "{"..table.concat(rows,",").."}"
end

local function visibleZombies(npc)
    return safely(function()
        local cell=getCell()
        local zombies=cell:getZombieList()
        local count=0
        local x,y,z=npc:getX(),npc:getY(),npc:getZ()
        if zombies:size()>10000 then return nil end
        for i=0,zombies:size()-1 do
            local other=zombies:get(i)
            local dx,dy=other:getX()-x,other:getY()-y
            if math.abs(other:getZ()-z)<0.5 and dx*dx+dy*dy<=144 and not other:isDead() then
                -- Missing vision API makes the count unknown, not zero.
                local seen=npc:CanSee(other)
                if type(seen)~="boolean" then return nil end
                if seen then count=count+1 end
            end
        end
        return count
    end)
end

function C.observe(npc)
    local facts={}
    local square=call(npc,"getCurrentSquare")
    local outside=call(square,"isOutside")
    if type(outside)=="boolean" then facts.npc_indoors=not outside end
    local vehicle,vehicleKnown=call(npc,"getVehicle")
    if vehicleKnown then facts.npc_in_vehicle=vehicle~=nil end
    local ground=call(npc,"isSitOnGround")
    local furniture=call(npc,"isSittingOnFurniture")
    if type(ground)=="boolean" and type(furniture)=="boolean" then facts.npc_sitting=ground or furniture end
    facts.visible_zombies_12_tiles=visibleZombies(npc)
    return facts
end

function C.capture(player,npc,line)
    -- Any observation/file failure leaves the normal conversation available.
    local writer
    local ok=pcall(function()
        local stamp=getTimestampMs()
        if not C.session then C.reset() end
        local npcName,playerName=name(npc),name(player)
        if not finite(stamp) or npcName=="" or playerName=="" or #tostring(line)>1200 then return end
        local metadata=object({captured_ms=stamp,session=C.session,npc=npcName,player=playerName,line=tostring(line)})
        local row=metadata:sub(1,-2)..',"facts":'..object(C.observe(npc))..'}'
        local recent={}
        for _,entry in ipairs(C.records) do
            if stamp>=entry.stamp and stamp-entry.stamp<=10000 then recent[#recent+1]=entry end
        end
        recent[#recent+1]={stamp=stamp,json=row}
        while #recent>8 do table.remove(recent,1) end
        C.records=recent
        local rows={}
        for _,entry in ipairs(recent) do rows[#rows+1]=entry.json end
        writer=getFileWriter(C.filename,true,false)
        if not writer then return end
        writer:write('{"schema":1,"records":['..table.concat(rows,",")..']}')
    end)
    if writer then safely(function() writer:close() end) end
    if not ok and not C.warned then
        print("[NPCFW Luna Context] Observation unavailable; normal dialogue continues.")
        C.warned=true
    end
end

function C.reset()
    C.records={}
    C.warned=false
    local stamp=safely(function() return getTimestampMs() end)
    if finite(stamp) then
        C.session=string.format("%.0f",stamp)
        -- Correlates read-only base-game event logs with this world session.
        print("[NPCFW Luna Context] session "..C.session)
    else C.session=nil end
end
if not C.eventsInstalled and Events and Events.OnGameStart then
    Events.OnGameStart.Add(C.reset)
    C.eventsInstalled=true
end
return C
