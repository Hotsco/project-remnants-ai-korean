require "NPCFW_LLM"
require "NPCFW_KoreanCommandParser"
require "NPCFW_LunaContext"
NPCFW_KoreanCommands = NPCFW_KoreanCommands or {}
local K = NPCFW_KoreanCommands
local P = NPCFW_KoreanCommandParser
K.version = "0.2.0"
K.requests = K.requests or {}
K.confirmations = K.confirmations or setmetatable({}, {__mode="k"})
K.historyFallback = K.historyFallback or setmetatable({}, {__mode="k"})
local function safely(fn,default)
    local ok,value=pcall(fn)
    if ok and value~=nil then return value end
    return default
end
local function call(obj,method,default)
    return safely(function() return obj[method](obj) end,default)
end
local function now()
    return safely(function() return getTimestampMs() end,0)
end
local function classify(item,script)
    local id=tostring(call(item,script and "getFullName" or "getFullType",""))
    local short=id:match("%.([^%.]+)$") or id
    if short:find("^Pills") or short=="Antibiotics" or short=="Vitamins" then return "medicine" end
    local kind=tostring(call(item,"getType",""))
    if kind=="Food" or safely(function() return instanceof(item,"Food") end,false) then return "food" end
    return "other"
end
local function catalogue()
    if K.catalogue then return K.catalogue end
    local out={}
    local items=safely(function() return getAllItems() end,nil)
    if items then
        for i=0,items:size()-1 do
            local item=items:get(i)
            local name=call(item,"getDisplayName",nil)
            if name and name~="" then out[#out+1]={name=tostring(name),kind=classify(item,true)} end
        end
    end
    -- Only cache an initialized catalogue; an early load must not freeze an empty one.
    if #out>0 then K.catalogue=out end
    return out
end
local function collect(container,out,seen,depth,budget)
    if not container or seen[container] or depth>5 or budget.n>=5000 then return end
    seen[container]=true
    local items=call(container,"getItems",nil)
    if not items then return end
    for i=0,items:size()-1 do
        if budget.n>=5000 then break end
        budget.n=budget.n+1
        local item=items:get(i)
        local name=call(item,"getDisplayName",nil) or call(item,"getName",nil)
        if name then out[#out+1]={name=tostring(name),kind=classify(item,false)} end
        collect(call(item,"getInventory",nil),out,seen,depth+1,budget)
    end
end
function K.context(player,npc,text)
    local ctx={names={},items={},partyCommand="none",sitting=false,inVehicle=false,driving=false}
    local full=call(npc,"getUsername","")
    if full~="" then
        ctx.names[#ctx.names+1]=full
        for part in full:gmatch("%S+") do if #part>=2 then ctx.names[#ctx.names+1]=part end end
    end
    table.sort(ctx.names,function(a,b) return #a>#b end)
    ctx.partyCommand=safely(function() return npcfwGetPartyCommand(npc) end,"none")
    ctx.sitting=call(npc,"isSitOnGround",false) or call(npc,"isSittingOnFurniture",false)
    local vehicle=call(npc,"getVehicle",nil)
    ctx.inVehicle=vehicle~=nil
    ctx.driving=vehicle~=nil and call(vehicle,"getDriver",nil)==npc
    local needsItems=false
    for _,rule in ipairs(NPCFW_KoreanCommandConfig) do
        if rule.kind=="item" or rule.kind=="recipe" then
            for _,alias in ipairs(rule.aliases) do
                if tostring(text):find(alias,1,true) then needsItems=true; break end
            end
        end
        if needsItems then break end
    end
    if needsItems then
        for _,entry in ipairs(catalogue()) do ctx.items[#ctx.items+1]=entry end
        local seen,budget={}, {n=0}
        collect(call(npc,"getInventory",nil),ctx.items,seen,0,budget)
        collect(call(player,"getInventory",nil),ctx.items,seen,0,budget)
    end
    return ctx
end
local function historyStore(npc)
    local data=call(npc,"getModData",nil)
    if data then
        data.NPCFW_KoreanCommandsHistory=data.NPCFW_KoreanCommandsHistory or {}
        return data.NPCFW_KoreanCommandsHistory
    end
    K.historyFallback[npc]=K.historyFallback[npc] or {}
    return K.historyFallback[npc]
end
local function historyKey(row)
    return tostring(row.when or "").."\n"..tostring(row.playerText or "").."\n"..tostring(row.npcReply or "")
end
local function recordHistory(player,npc,request)
    if not K.rawHistory or not request then return end
    local history=safely(function() return K.rawHistory(player,npc) end,nil)
    if not history then return end
    local row
    for _,entry in ipairs(history) do if entry.playerText==request.canonical then row=entry end end
    if not row then return end
    local entries=historyStore(npc)
    entries[#entries+1]={key=historyKey(row),text=request.original}
    while #entries>64 do table.remove(entries,1) end
end
local function rememberOutcome(player,npc,result)
    if not result then return end
    if result.orderStatus=="CONFIRMATION" then
        K.confirmations[npc]={player=player,untilMs=now()+120000}
    elseif result.status~="PENDING" then K.confirmations[npc]=nil end
end
local answers={ ["\236\157\145"]="yes", ["\234\183\184\235\158\152"]="yes", ["\235\132\164"]="yes", ["\236\162\139\236\149\132"]="yes", ["\237\153\149\236\157\184"]="yes", ["\237\149\180"]="yes", ["\237\149\180\236\164\152"]="yes", ["\236\149\132\235\139\136"]="no", ["\236\149\132\235\139\136\236\154\148"]="no", ["\236\183\168\236\134\140"]="no", ["\237\149\152\236\167\128\235\167\136"]="no" }
function K.installBridges()
    if npcfwStartTalk and npcfwStartTalk~=K.startWrapper then
        local original=npcfwStartTalk
        K.startWrapper=function(player,npc,text)
            local raw=tostring(text or "")
            local settings=SandboxVars and SandboxVars.ProjectRemnants
            if settings and settings.EnableLLMActions==false then
                if NPCFW_LunaContext then pcall(NPCFW_LunaContext.capture,player,npc,raw) end
                return original(player,npc,raw)
            end
            local translated,reason
            local pending=K.confirmations[npc]
            if pending and pending.player==player and now()<pending.untilMs then
                local answer=answers[P.compact(raw):gsub("[!?.]","")]
                if answer then translated={text=answer,id="confirmation"} end
            end
            if not pending or now()>=pending.untilMs then
                local ok,result,err=pcall(function() return P.translate(raw,K.context(player,npc,raw)) end)
                if not ok then
                    print("[NPCFW Korean Commands] Local parser error: "..tostring(result))
                    return {status="REJECTED",reason="\237\149\156\234\181\173\236\150\180 \235\170\133\235\160\185\236\157\132 \237\149\180\236\132\157\237\149\152\236\167\128 \235\170\187\237\150\136\236\138\181\235\139\136\235\139\164. \235\172\184\236\158\165\236\157\132 \236\167\167\234\178\140 \235\139\164\236\139\156 \236\158\133\235\160\165\237\149\180\236\163\188\236\132\184\236\154\148."}
                end
                translated,reason=result,err
            end
            if reason then return {status="REJECTED",reason=reason} end
            local canonical=translated and translated.text or raw
            if NPCFW_LunaContext then pcall(NPCFW_LunaContext.capture,player,npc,canonical) end
            local result=original(player,npc,canonical)
            if result then
                rememberOutcome(player,npc,result)
                if translated then
                    result.text=raw
                    local request={original=raw,canonical=canonical,player=player,npc=npc}
                    if result.status=="ACCEPTED" and result.requestId then
                        K.requests[result.requestId]=request
                    elseif result.status=="READY" then recordHistory(player,npc,request) end
                    print("[NPCFW Korean Commands] mapped "..translated.id)
                end
            end
            return result
        end
        npcfwStartTalk=K.startWrapper
    end
    if npcfwPollTalk and npcfwPollTalk~=K.pollWrapper then
        local original=npcfwPollTalk
        K.pollWrapper=function(requestId,player,npc)
            local result=original(requestId,player,npc)
            rememberOutcome(player,npc,result)
            if result and result.status~="PENDING" then
                if result.status=="READY" then recordHistory(player,npc,K.requests[requestId]) end
                K.requests[requestId]=nil
            end
            return result
        end
        npcfwPollTalk=K.pollWrapper
    end
    if npcfwGetTalkHistory and npcfwGetTalkHistory~=K.historyWrapper then
        local original=npcfwGetTalkHistory
        K.rawHistory=original
        K.historyWrapper=function(player,npc)
            local history=original(player,npc)
            if not history then return history end
            local entries=historyStore(npc)
            for _,row in ipairs(history) do
                local key=historyKey(row)
                for i=#entries,1,-1 do
                    if entries[i].key==key then row.playerText=entries[i].text; break end
                end
            end
            return history
        end
        npcfwGetTalkHistory=K.historyWrapper
    end
end
function K.install()
    K.installBridges()
    if NPCFW_LLM and NPCFW_LLM.submit and NPCFW_LLM.submit~=K.submitWrapper then
        local original=NPCFW_LLM.submit
        K.submitWrapper=function(player,npc,text)
            K.installBridges()
            return original(player,npc,text)
        end
        NPCFW_LLM.submit=K.submitWrapper
    end
end
K.install()
if not K.eventsInstalled then
    if Events and Events.OnGameStart then Events.OnGameStart.Add(K.install) end
    K.eventsInstalled=true
end
return K
