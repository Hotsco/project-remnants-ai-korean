-- Pure local recognition. This module never calls an LLM or changes game state.
require "NPCFW_KoreanCommandConfig"
NPCFW_KoreanCommandParser = {}
local P = NPCFW_KoreanCommandParser
local function trim(s) return (tostring(s or ""):gsub("^%s+", ""):gsub("%s+$", "")) end
local function compact(s) return (trim(s):lower():gsub("%s+", "")) end
local function has(s, part) return s:find(part, 1, true) ~= nil end
local function starts(s, part) return s:sub(1, #part) == part end
local function ends(s, part) return part ~= "" and s:sub(-#part) == part end
P.compact = compact
local function withoutEnd(s, values)
    s = trim(s)
    for _, v in ipairs(values) do
        if ends(s, v) then return trim(s:sub(1, #s - #v)) end
    end
    return s
end
local function clean(s)
    return trim((tostring(s or ""):gsub("[!?.~,]+", " "):gsub("%s+", " ")))
end
local particles = {"\236\156\188\235\161\156", "\236\151\144\234\178\140", "\237\149\156\237\133\140", "\234\185\140\236\167\128", "\236\151\144\236\132\156", "\236\157\132", "\235\165\188", "\236\157\128", "\235\138\148", "\236\157\180", "\234\176\128", "\235\161\156", "\236\151\144"}
local fillers = {"\236\154\176\235\166\172 \234\183\128\236\151\188\235\145\165\236\157\180", "\236\154\176\235\166\172\234\183\128\236\151\188\235\145\165\236\157\180", "\234\183\128\236\151\188\235\145\165\236\157\180", "\235\182\128\237\131\129\236\157\184\235\141\176", "\235\175\184\236\149\136\237\149\156\235\141\176", "\234\183\184\235\159\172\235\169\180", "\234\183\184\235\159\172\235\139\136\234\185\140", "\234\183\184\235\159\188", "\236\157\188\235\139\168", "\236\157\180\236\160\156", "\236\150\180\236\132\156", "\235\185\168\235\166\172", "\236\160\156\235\176\156", "\235\168\188\236\160\128", "\236\154\176\235\166\172", "\236\158\144", "\236\162\128"}
local function stripAddress(s, ctx, preserveSpeed)
    s = trim(s)
    for _ = 1, 12 do
        local before = s
        for _, name in ipairs(ctx.names or {}) do
            if name ~= "" and starts(s, name) then
                s = trim(s:sub(#name + 1))
                if starts(s, "\236\149\132") or starts(s, "\236\149\188") then s = trim(s:sub(2)) end
                s = trim(s:gsub("^[,!:]+", ""))
                break
            end
        end
        for _, word in ipairs(fillers) do
            local protected=(preserveSpeed and word=="\235\185\168\235\166\172") or (word=="\236\158\144" and #s>1 and not s:sub(2,2):match("%s"))
            if not protected and starts(s, word) then s = trim(s:sub(#word + 1)); break end
        end
        if before == s then break end
    end
    s = withoutEnd(s, {" \236\162\128", "\236\162\128", " \237\149\156\235\178\136", " \237\149\156 \235\178\136"})
    return trim(s)
end
local function value(s, ctx)
    return withoutEnd(stripAddress(s, ctx), particles)
end
local function isNarrative(s)
    if s:find('["\']') or has(s, "\226\128\156") or has(s, "\226\128\157") then return true end
    local t = compact(s)
    for _, word in ipairs({"\235\157\188\234\179\160", "\235\157\188\235\138\148", "\235\157\188\235\141\152", "\237\149\152\236\158\144\234\179\160", "\237\149\152\235\157\188\234\179\160", "\237\149\180\235\139\172\235\157\188", "\237\150\136\236\158\150", "\237\150\136\236\150\180", "\237\150\136\236\167\128", "\237\150\136\235\141\152", "\237\150\136\235\132\164", "\237\150\136\235\130\152", "\237\150\136\236\157\140", "\237\149\152\235\141\152", "\237\149\160\235\149\140", "\237\149\156\235\139\164\235\169\180", "\237\149\152\235\169\180", "\237\149\152\235\160\164\235\169\180", "\237\149\180\235\143\132", "\235\168\185\236\150\180\235\143\132", "\235\167\136\236\133\148\235\143\132", "\237\149\160\236\136\152", "\237\149\160\236\164\132", "\234\176\128\235\138\165", "\236\150\184\236\160\156", "\236\150\180\235\148\148", "\236\150\188\235\167\136", "\235\172\180\236\138\168", "\236\150\180\235\150\187\234\178\140", "\236\153\156", "\237\149\132\236\154\148", "\236\162\139\234\178\160", "\236\139\182\236\150\180", "\236\139\182\235\139\164", "\234\178\160\235\132\164", "\235\130\180\236\157\188", "\235\130\152\236\164\145\236\151\144", "\236\157\180\235\148\176", "\236\150\180\236\160\156", "\236\149\132\234\185\140", "\236\167\128\235\167\136", "\236\167\128\235\167\144", "\235\167\144\236\149\132", "\235\167\144\234\179\160", "\236\149\138\236\149\132", "\236\149\138\234\179\160", "\236\149\132\235\139\136", "\234\183\184\235\167\140\236\155\131", "\234\183\184\235\167\140\235\134\128"}) do
        if has(t, word) then return true end
    end
    return false
end
local basicTails = {"", "\237\149\180", "\237\149\152\236\158\144", "\237\149\152\236\158\144\236\154\148", "\237\149\180\236\164\152", "\237\149\180\236\164\152\236\154\148", "\237\149\180\235\180\144", "\237\149\180\235\180\144\236\164\152", "\237\149\180\236\164\132\235\158\152", "\237\149\180\236\164\132\235\158\152\236\154\148", "\237\149\180\236\163\188\236\132\184\236\154\148", "\237\149\180\236\163\188\236\132\184\236\154\148\236\154\148", "\237\149\152\235\160\180", "\237\149\152\235\157\188\234\179\160\236\154\148", "\236\162\128", "\236\162\128\237\149\180", "\236\162\128\237\149\152\236\158\144", "\236\162\128\237\149\180\236\164\152", "\236\162\128\237\149\180\235\180\144", "\235\182\128\237\131\129\237\149\180", "\235\182\128\237\131\129\237\149\180\236\154\148", "\237\149\180\236\163\188\235\157\188", "\237\149\152\234\179\160\236\158\136\236\150\180", "\237\149\180\235\179\180\236\158\144", "\237\149\180\235\179\188\235\158\152", "\237\149\180\235\143\132\235\143\188"}
local verbTails = {"", "\236\164\152", "\236\164\152\236\154\148", "\235\180\144", "\235\180\144\236\164\152", "\235\180\144\236\154\148", "\236\163\188\236\132\184\236\154\148", "\236\163\188\235\157\188", "\236\164\132\235\158\152", "\236\164\132\235\158\152\236\154\148", "\235\180\144\236\164\132\235\158\152", "\235\180\144\236\164\152\236\154\148", "\235\157\188", "\236\154\148", "\236\164\152\236\160\156\235\176\156"}
local tailById = {
    loot={"\236\176\190\236\149\132", "\236\176\190\236\149\132\236\164\152", "\236\176\190\236\149\132\235\180\144", "\236\176\190\236\158\144", "\236\136\152\236\131\137\237\149\180", "\236\136\152\236\131\137\237\149\152\236\158\144", "\236\162\128\236\176\190\236\149\132\236\164\152", "\236\162\128\236\176\190\236\149\132\235\180\144", "\236\162\128\236\136\152\236\131\137\237\149\180", "\234\181\172\237\149\180\236\164\152", "\236\177\153\234\178\168\236\164\152"},
    stand={""}, sleep={""},
    stop_loot={"", "\237\149\180", "\237\149\152\236\158\144", "\237\149\180\236\164\152", "\236\176\190\236\149\132", "\236\176\190\236\158\144", "\236\176\190\236\149\132\235\143\132\235\143\188"},
    maintain_all={"", "\236\160\144\234\178\128", "\236\160\144\234\178\128\237\149\180", "\236\160\144\234\178\128\237\149\180\236\164\152", "\234\180\128\235\166\172\237\149\180", "\236\177\153\234\178\168", "\236\177\153\234\178\168\236\164\152"},
    maintain_ammo={"\236\160\144\234\178\128", "\236\160\144\234\178\128\237\149\180", "\236\160\144\234\178\128\237\149\180\236\164\152", "\235\179\180\236\182\169", "\235\179\180\236\182\169\237\149\180", "\235\179\180\236\182\169\237\149\180\236\164\152", "\236\177\153\234\178\168\236\164\152"},
    maintain_battery={"\236\160\144\234\178\128", "\236\160\144\234\178\128\237\149\180", "\236\160\144\234\178\128\237\149\180\236\164\152", "\235\179\180\236\182\169", "\235\179\180\236\182\169\237\149\180", "\235\179\180\236\182\169\237\149\180\236\164\152", "\236\177\153\234\178\168\236\164\152"},
    resupply={"\236\177\132\236\155\140", "\236\177\132\236\155\140\236\164\152", "\236\177\132\236\155\140\235\180\144", "\236\177\132\236\154\176\236\158\144", "\235\179\180\236\182\169\237\149\180", "\236\158\165\236\160\132\237\149\180", "\236\158\165\236\160\132\237\149\180\236\164\152", "\236\162\128\236\177\132\236\155\140\236\164\152"},
    fill_water={"\236\177\132\236\155\140", "\236\177\132\236\155\140\236\164\152", "\236\177\132\236\155\140\235\180\144", "\236\177\132\236\154\176\236\158\144", "\236\162\128\236\177\132\236\155\140\236\164\152", "\235\179\180\236\182\169\237\149\180", "\235\176\155\236\149\132\236\164\152"},
    driver={"\236\158\161\236\149\132", "\236\158\161\236\149\132\236\164\152", "\236\158\161\236\158\144", "\235\167\161\236\149\132", "\235\167\161\236\149\132\236\164\152"},
    speed={"\234\176\128", "\234\176\128\236\158\144", "\234\176\128\236\164\152", "\235\139\172\235\160\164", "\235\139\172\235\166\172\236\158\144", "\236\154\180\236\160\132\237\149\180", "\236\154\180\236\160\132\237\149\180\236\164\152"},
    job={"\235\139\180\235\139\185\237\149\180", "\235\139\180\235\139\185\237\149\180\236\164\152", "\235\167\161\236\149\132", "\235\167\161\236\149\132\236\164\152", "\235\167\161\236\149\132\236\164\132\235\158\152"},
    guard_post={"\236\132\164\236\160\149", "\236\132\164\236\160\149\237\149\180", "\236\132\164\236\160\149\237\149\180\236\164\152", "\236\160\149\237\149\180", "\236\160\149\237\149\180\236\164\152"},
}
local function listed(t, list)
    for _, v in ipairs(list or {}) do if t == v then return true end end
    return false
end
local function allowedTail(rule, tail)
    local t = compact(clean(tail))
    -- Harmless trailing vocatives are stripped by the caller.
    if listed(t, basicTails) or listed(t, verbTails) then return true end
    if listed(t, tailById[rule.id]) then return true end
    if starts(rule.id,"loot_") and listed(t,tailById.loot) then return true end
    if starts(rule.id,"speed_") and listed(t,tailById.speed) then return true end
    if starts(rule.id,"job_") and listed(t,tailById.job) then return true end
    return false
end
local function canonicalPlace(s)
    local t = compact(s)
    if t=="\236\151\172\234\184\176\236\132\156" then return "me" end
    if t=="\236\160\128\234\184\176\236\132\156" or t=="\234\177\176\234\184\176\236\132\156" then return "that spot" end
    local names = { ["\236\151\172\234\184\176"]="me", ["\236\157\180\235\166\172"]="me", ["\235\130\180\236\170\189"]="me", ["\235\130\180\236\152\134"]="me", ["\236\160\128\234\184\176"]="that spot", ["\234\177\176\234\184\176"]="that spot", ["\236\160\128\236\170\189"]="that spot", ["\234\184\176\236\167\128"]="base", ["\236\167\145"]="home", ["\236\149\136\236\160\132\234\176\128\236\152\165"]="safehouse", ["\235\178\140\235\170\169\236\158\165"]="lumber area", ["\235\178\140\235\170\169\234\181\172\236\151\173"]="lumber area", ["\235\131\137\236\158\165\234\179\160"]="fridge", ["\235\179\180\234\180\128\237\149\168"]="container", ["\236\131\129\236\158\144"]="crate", ["\236\157\180\235\179\180\234\180\128\237\149\168"]="this container", ["\236\160\128\235\179\180\234\180\128\237\149\168"]="that container", ["\236\157\180\236\131\129\236\158\144"]="this container", ["\236\160\128\236\131\129\236\158\144"]="that container", ["\235\130\152"]="me", ["\235\130\152\237\149\156\237\133\140"]="me", ["\235\130\152\236\151\144\234\178\140"]="me", ["\235\130\152\235\165\188"]="me", ["\235\132\136"]="self", ["\235\132\136\236\158\144\236\139\160"]="self" }
    if names[t] then return names[t] end
    local number = t:match("^\235\134\141\236\158\165(%d+)$") or t:match("^\234\178\189\236\158\145\236\167\128(%d+)$")
    if number then return "farm " .. number end
    return trim(s)
end
local simplePrefixes = {
    stop_loot={"\236\136\152\236\131\137", "\236\136\152\236\131\137\236\157\128", "\236\176\190\235\138\148\234\177\180", "\236\157\180\236\160\156\236\136\152\236\131\137"},
    maintain_inspect={"\236\158\165\235\185\132", "\236\158\165\235\185\132\235\165\188", "\235\172\180\234\184\176", "\235\172\180\234\184\176\235\165\188"},
    maintain_all={"\236\158\165\235\185\132", "\236\158\165\235\185\132\235\165\188"},
    cqb_on={"\234\183\188\236\160\145"}, cqb_off={"\234\181\144\236\160\132", "\234\183\188\236\160\145\234\181\144\236\160\132"},
    corpses={"\236\139\156\236\178\180", "\236\139\156\236\178\180\235\165\188", "\236\163\188\235\179\128\236\139\156\236\178\180", "\236\139\156\236\178\180\235\147\164"},
    wring={"\236\152\183", "\236\152\183\236\157\132", "\236\160\150\236\157\128\236\152\183", "\236\160\150\236\157\128\236\152\183\236\157\132"},
    wash_clothes={"\236\152\183", "\236\152\183\236\157\132"},
    fill_water={"\236\154\169\234\184\176\236\151\144", "\235\172\188\237\134\181\236\151\144", "\235\172\188\235\179\145\236\151\144"},
    stance_aggressive={"\236\160\132\237\136\172", "\237\131\156\236\132\184"}, stance_defensive={"\236\160\132\237\136\172", "\237\131\156\236\132\184"},
    roe_melee={"\236\160\132\237\136\172", "\236\160\132\237\136\172\235\138\148"}, roe_ranged={"\236\160\132\237\136\172", "\236\160\132\237\136\172\235\138\148"}, roe_mixed={"\236\160\132\237\136\172", "\236\160\132\237\136\172\235\138\148", "\236\139\184\236\155\128\236\157\128", "\236\139\184\236\155\128"},
}
local function simplePrefix(rule, before)
    local t = compact(before)
    if t == "" or t=="\235\132\136" or t=="\235\132\136\235\138\148" then return true end
    if listed(t, simplePrefixes[rule.id]) then return true end
    if starts(rule.id,"speed_") and listed(t,{"\236\176\168", "\236\176\168\235\165\188", "\236\154\180\236\160\132", "\236\154\180\236\160\132\236\157\128"}) then return true end
    if starts(rule.id,"loot_") and listed(t,{"\236\151\172\234\184\176", "\236\151\172\234\184\176\236\132\156", "\236\157\180\234\177\180\235\172\188", "\236\157\180\234\177\180\235\172\188\236\151\144\236\132\156"}) then return true end
    return false
end
local function removeOnce(s, word)
    local a,b=s:find(word,1,true)
    if a then return trim(s:sub(1,a-1).." "..s:sub(b+1)) end
    return s
end
local function itemMatch(s, ctx)
    local t=compact(s)
    local best, length, ambiguous=nil,0,false
    for _, item in ipairs(ctx.items or {}) do
        local n=compact(item.name)
        if n~="" and has(t,n) then
            if #n > length then best=item; length=#n; ambiguous=false
            elseif #n == length and best and (n~=compact(best.name) or item.kind~=best.kind) then ambiguous=true end
        end
    end
    if ambiguous then return nil,"\235\172\188\234\177\180\236\157\132 \237\149\152\235\130\152\236\148\169 \236\167\128\236\160\149\237\149\180\236\163\188\236\132\184\236\154\148." end
    if best then
        -- Two separate items must not silently collapse to the longest name.
        for _, other in ipairs(ctx.items or {}) do
            local n=compact(other.name)
            if n~="" and has(t,n) and not has(compact(best.name),n) then
                return nil,"\235\172\188\234\177\180\236\157\132 \237\149\152\235\130\152\236\148\169 \236\167\128\236\160\149\237\149\180\236\163\188\236\132\184\236\154\148."
            end
        end
    end
    return best
end
local function takeClause(s, marker)
    local a,b=s:find(marker,1,true)
    if not a then return nil,s end
    return trim(s:sub(1,a-1)), trim(s:sub(b+1))
end
local function itemCommand(rule,before,ctx)
    local s=before
    local source,target,destination
    source,s=takeClause(s,"\236\151\144\236\132\156")
    local marker=has(s,"\236\151\144\234\178\140") and "\236\151\144\234\178\140" or (has(s,"\237\149\156\237\133\140") and "\237\149\156\237\133\140" or nil)
    if marker then target,s=takeClause(s,marker) end
    if target then target=canonicalPlace(value(target,ctx)) end
    if source then source=canonicalPlace(value(source,ctx)) end
    if rule.id=="store" or rule.id=="transfer" then
        local a,b=s:find("\236\151\144 ",1,true)
        if a then destination=canonicalPlace(value(s:sub(1,a-1),ctx));s=trim(s:sub(b+1)) end
    end
    local quantity=s:match("(%d+)%s*\234\176\156") or s:match("(%d+)%s*\236\157\184\235\182\132")
    if quantity then s=s:gsub("%d+%s*\234\176\156",""):gsub("%d+%s*\236\157\184\235\182\132","") end
    for _, pair in ipairs({{"\237\149\156 \234\176\156",1},{"\237\149\156\234\176\156",1},{"\235\145\144 \234\176\156",2},{"\235\145\144\234\176\156",2},{"\236\132\184 \234\176\156",3},{"\236\132\184\234\176\156",3}}) do
        if has(s,pair[1]) then quantity=tostring(pair[2]); s=removeOnce(s,pair[1]); break end
    end
    local all=has(s,"\236\160\132\235\182\128") or has(s,"\235\170\168\235\145\144")
    s=removeOnce(removeOnce(s,"\236\160\132\235\182\128"),"\235\170\168\235\145\144")
    local item,err=itemMatch(s,ctx)
    if err then return nil,err end
    local itemName=item and item.name or value(s,ctx)
    if not item and listed(compact(itemName),{"\236\157\180\236\149\188\234\184\176","\236\150\152\234\184\176","\235\130\180\236\157\180\236\149\188\234\184\176","\235\130\180\236\150\152\234\184\176","\235\167\144","\235\130\180\235\167\144","\236\134\140\235\166\172","\236\131\157\234\176\129","\236\154\149\236\139\172","\235\167\136\236\157\140","\237\157\172\235\167\157","\234\178\129","\236\160\149\236\139\160"}) then return nil end
    if rule.id=="equip" and not item and itemName~="" then return nil end
    if item then
        local rest=trim(removeOnce(s,item.name))
        rest=stripAddress(rest,ctx)
        if starts(rest,"\236\157\132") or starts(rest,"\235\165\188") then rest=trim(rest:sub(2)) end
        if rest~="" and (rule.id=="store" or rule.id=="transfer") and not destination then
            destination=canonicalPlace(value(rest,ctx))
        elseif rest~="" and compact(rest)~=compact(item.name) then
            return nil,"\235\172\188\234\177\180 \236\157\180\235\166\132\234\179\188 \237\149\132\236\154\148\237\149\156 \235\140\128\236\131\129\235\167\140 \236\167\167\234\178\140 \236\167\128\236\160\149\237\149\180\236\163\188\236\132\184\236\154\148."
        end
    end
    if rule.id=="resupply" and itemName=="" then return "fill magazines" end
    if itemName=="" or listed(compact(itemName),{"\234\183\184\234\177\176","\236\157\180\234\177\176","\234\183\184\234\178\131","\236\160\128\234\178\131","\236\157\180\234\178\131","\236\149\132\235\172\180\234\177\176\235\130\152"}) then
        return nil,"\235\172\188\234\177\180 \236\157\180\235\166\132\236\157\132 \237\149\168\234\187\152 \235\167\144\237\149\180\236\163\188\236\132\184\236\154\148."
    end
    if rule.id=="consume" then
        if not item then return nil,"\236\157\140\236\139\157\236\157\184\236\167\128 \236\149\189\236\157\184\236\167\128 \237\153\149\236\157\184\237\149\160 \236\136\152 \236\151\134\236\150\180\236\154\148. \236\139\164\236\160\156 \236\149\132\236\157\180\237\133\156 \236\157\180\235\166\132\236\157\132 \235\167\144\237\149\180\236\163\188\236\132\184\236\154\148." end
        if all or (quantity and quantity~="1") then return nil,"\235\168\185\234\177\176\235\130\152 \235\179\181\236\154\169\237\149\152\235\138\148 \235\170\133\235\160\185\236\157\128 \237\149\156 \235\178\136\236\151\144 \237\149\152\235\130\152\236\148\169 \236\167\128\236\160\149\237\149\180\236\163\188\236\132\184\236\154\148." end
        local cmd
        if item.kind=="medicine" then cmd="take medicine "..item.name end
        if item.kind=="food" then cmd="eat "..item.name end
        if not cmd then return nil,"\235\168\185\236\157\132 \236\136\152 \236\158\136\235\138\148 \236\157\140\236\139\157\236\157\180\235\130\152 \235\179\181\236\154\169\237\149\160 \236\149\189\236\157\132 \236\167\128\236\160\149\237\149\180\236\163\188\236\132\184\236\154\148." end
        if source and source~="" then return "start the following task: "..cmd.." from "..source end
        return cmd
    end
    if rule.id=="drink" and itemName=="\235\172\188" then itemName="water" end
    local named=(all and "all " or (quantity and quantity.." " or ""))..itemName
    local command=rule.canonical.." "..named
    if rule.id=="resupply" then command="fill "..named.." magazines" end
    if rule.id=="store" or rule.id=="transfer" then
        if not destination or destination=="" then return nil,"\235\179\180\234\180\128\237\149\152\234\177\176\235\130\152 \236\152\174\234\184\184 \235\170\169\236\160\129\236\167\128 \235\179\180\234\180\128\237\149\168\236\157\132 \237\149\168\234\187\152 \235\167\144\237\149\180\236\163\188\236\132\184\236\154\148." end
        if rule.id=="transfer" and (not source or source=="") then return nil,"\236\182\156\235\176\156 \235\179\180\234\180\128\237\149\168\235\143\132 \237\149\168\234\187\152 \235\167\144\237\149\180\236\163\188\236\132\184\236\154\148." end
    end
    if source and source~="" then command=command.." from "..source end
    if destination and destination~="" then command=command.." to "..destination end
    if target and target~="" then
        if rule.id=="resupply" then command=command.." and give them to "..target
        elseif rule.id=="cook" then command=command.." for "..target
        else command=command.." to "..target end
    elseif rule.id=="give" then command=command.." to me" end
    return command
end
local function build(rule,before,ctx)
    local id=rule.id
    if id=="stand" and not ctx.sitting and ctx.partyCommand~="break" then return nil end
    if id=="stop_loot" and ctx.partyCommand~="loot" then return nil end
    if starts(id,"speed_") and not ctx.driving then return nil end
    if id=="exit" and not ctx.inVehicle then return nil end
    if id=="stop_driving" and not ctx.driving then return nil end
    if rule.kind=="simple" then
        if not simplePrefix(rule,before) then return nil end
        return rule.canonical
    end
    if rule.kind=="item" or rule.kind=="recipe" then return itemCommand(rule,before,ctx) end
    local arg=canonicalPlace(value(before,ctx))
    if rule.kind=="location" then
        if arg=="" then return nil,"\235\170\169\236\160\129\236\167\128 \236\157\180\235\166\132\236\157\180\235\130\152 \226\128\152\236\151\172\234\184\176\226\128\153\235\165\188 \237\149\168\234\187\152 \235\167\144\237\149\180\236\163\188\236\132\184\236\154\148." end
        if id=="guard_post" then return "set "..arg.." as your guard post" end
        return rule.canonical.." "..arg
    end
    if rule.kind=="location_optional" then
        return rule.canonical..(arg~="" and " at "..arg or "")
    end
    if rule.kind=="person_optional" then
        if arg=="" then arg="me" end
        if id=="treat" then return "patch "..arg.." up" end
        if id=="regroup" and arg=="me" then return "regroup" end
        if id=="regroup" or (id=="follow_vehicle" and arg~="me") then
            return "start the following task: "..rule.canonical.." with "..arg
        end
        return rule.canonical.." "..arg
    end
    if rule.kind=="container" then
        if arg=="" then return nil,"\237\153\149\236\157\184\237\149\160 \235\131\137\236\158\165\234\179\160\235\130\152 \235\179\180\234\180\128\237\149\168\236\157\132 \236\167\128\236\160\149\237\149\180\236\163\188\236\132\184\236\154\148." end
        return rule.canonical.." "..arg
    end
    if rule.kind=="vehicle_optional" then
        if arg=="\236\176\168" or arg=="\236\176\168\235\159\137" then arg="" end
        return "get in "..(arg~="" and arg.." " or "").."as "..(id=="driver" and "driver" or "passenger")
    end
    if rule.kind=="hostile" then
        if arg=="" then return nil,"\234\179\181\234\178\169\237\149\160 \236\160\129\236\157\132 \236\167\128\236\160\149\237\149\180\236\163\188\236\132\184\236\154\148. \236\152\136: \236\160\128 \236\162\128\235\185\132 \235\149\140\235\160\164." end
        if listed(compact(arg),{"\236\160\128\236\162\128\235\185\132","\234\183\184\236\162\128\235\185\132","\236\160\128\235\134\136","\234\183\184\235\134\136","\236\160\128\235\133\128\236\132\157","\234\183\184\235\133\128\236\132\157"}) then arg="that zombie" end
        return "attack "..arg
    end
end
function P.translate(text,ctx)
    ctx=ctx or {}
    local raw=trim(text)
    if raw=="" or isNarrative(raw) then return nil end
    local s=stripAddress(clean(raw),ctx,true)
    local c=compact(s)
    if has(c,"\234\183\184\235\166\172\234\179\160") or has(c,"\237\149\156\235\139\164\236\157\140") or has(c,"\237\149\156\235\146\164") or (has(c,"\237\149\152\234\179\160") and not ends(c,"\237\149\152\234\179\160\236\158\136\236\150\180")) then
        return nil,"\235\170\133\235\160\185\236\157\128 \237\149\156 \235\143\153\236\158\145\236\148\169 \235\167\144\237\149\180\236\163\188\236\132\184\236\154\148."
    end
    local candidates={}
    for _,rule in ipairs(NPCFW_KoreanCommandConfig) do
        for _,alias in ipairs(rule.aliases) do
            local at,finish=s:find(alias,1,true)
            if at and not has(compact(s),"\236\149\136"..compact(alias)) then
                local before=stripAddress(s:sub(1,at-1),ctx)
                local tail=stripAddress(s:sub(finish+1),ctx)
                if allowedTail(rule,tail) then
                    -- Do not split a word such as '\235\147\164\236\150\180\234\176\132\235\139\164' into an equipment order.
                    local command,reason=build(rule,before,ctx)
                    if command or reason then
                        candidates[#candidates+1]={text=command,reason=reason,id=rule.id,label=rule.label,score=#compact(alias),before=before}
                    end
                end
            end
        end
    end
    table.sort(candidates,function(a,b) return a.score>b.score end)
    local winner=candidates[1]
    if not winner then return nil end
    for _,other in ipairs(candidates) do
        if other.id~=winner.id and other.score==winner.score then
            return nil,"\236\151\172\235\159\172 \235\170\133\235\160\185\236\156\188\235\161\156 \237\149\180\236\132\157\235\144\160 \236\136\152 \236\158\136\236\150\180\236\154\148. \237\149\156 \235\143\153\236\158\145\236\148\169 \235\167\144\237\149\180\236\163\188\236\132\184\236\154\148."
        end
    end
    if not winner.text then return nil,winner.reason end
    -- Keep unknown ordinary conversation on the original dialogue path.
    return winner
end
return P
