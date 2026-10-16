import java.io.*;
import java.lang.reflect.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

/** Uses the user's installed Remnants reader; never writes the supplied save. */
public class NpcProfileCodec {
    static Class<?> dataClass;
    static Method loader, limiter;
    static class Row {
        String id, name, profile;
        boolean female, dead;
        int start, end;
    }
    static class Save {
        int version;
        List<Row> rows = new ArrayList<>();
    }
    static String field(Object o, String key) throws Exception {
        Object value = dataClass.getField(key).get(o);
        return value == null ? "" : value.toString();
    }
    static Save parse(byte[] bytes) throws Exception {
        if (bytes.length > 64 * 1024 * 1024) throw new IOException("SAVE_TOO_LARGE");
        DataInputStream in = new DataInputStream(new ByteArrayInputStream(bytes));
        if (in.readInt() != 0x4e504346) throw new IOException("UNKNOWN_SAVE_FORMAT");
        Save save = new Save();
        save.version = in.readInt();
        int count = in.readInt();
        if (save.version < 4 || count < 0 || count > 10000) throw new IOException("UNKNOWN_SAVE_FORMAT");
        in.readUTF();
        Set<String> ids = new HashSet<>();
        for (int i = 0; i < count; i++) {
            Row row = new Row();
            row.start = bytes.length - in.available();
            Object npc = loader.invoke(null, in, save.version);
            row.end = bytes.length - in.available();
            row.id = field(npc, "npcId");
            row.name = field(npc, "displayName");
            row.profile = field(npc, "characterProfile");
            row.female = dataClass.getField("isFemale").getBoolean(npc);
            row.dead = dataClass.getField("isDead").getBoolean(npc);
            if (row.id.isEmpty() || !ids.add(row.id)) throw new IOException("DUPLICATE_NPC_ID");
            save.rows.add(row);
        }
        if (in.available() != 0) throw new IOException("UNREAD_SAVE_DATA");
        return save;
    }
    static byte[] utf(String value) throws Exception {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        new DataOutputStream(out).writeUTF(value);
        return out.toByteArray();
    }
    static byte[] patch(byte[] bytes, Save before, String id, String text) throws Exception {
        if (!text.equals((String)limiter.invoke(null, text))) throw new IOException("PROFILE_LIMIT");
        Row target = null;
        for (Row row : before.rows) if (row.id.equals(id)) target = row;
        if (target == null) throw new IOException("NPC_NOT_FOUND");
        if (target.profile.equals(text)) return bytes;
        byte[] old = utf(target.profile), replacement = utf(text);
        int attempts = 0;
        // Locate by content inside this NPC's record, then prove the installed
        // reader treats that field as its profile. No fixed offsets or release gate.
        for (int offset = target.end - old.length; offset >= target.start; offset--) {
            boolean same = true;
            for (int i = 0; i < old.length; i++) if (bytes[offset+i] != old[i]) { same = false; break; }
            if (!same) continue;
            if (++attempts > 256) break;
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            out.write(bytes, 0, offset);
            out.write(replacement);
            out.write(bytes, offset + old.length, bytes.length - offset - old.length);
            byte[] changed = out.toByteArray();
            try {
                Save after = parse(changed);
                boolean valid = before.version == after.version && before.rows.size() == after.rows.size();
                for (int i = 0; valid && i < before.rows.size(); i++) {
                    Row a = before.rows.get(i), b = after.rows.get(i);
                    valid = a.id.equals(b.id) && a.name.equals(b.name) && a.female == b.female && a.dead == b.dead
                        && b.profile.equals(a.id.equals(id) ? text : a.profile);
                }
                if (valid) return changed;
            } catch (Exception rejected) { /* This is not the profile field. */ }
        }
        throw new IOException("PROFILE_FIELD_NOT_VERIFIED");
    }
    static String quote(String value) {
        StringBuilder out = new StringBuilder("\"");
        for (char c : value.toCharArray()) {
            if (c == '"' || c == '\\') out.append('\\').append(c);
            else if (c < 32) out.append(String.format("\\u%04x", (int)c));
            else out.append(c);
        }
        return out.append('"').toString();
    }
    static String json(Save save) throws Exception {
        int limit = ((String)limiter.invoke(null, "x".repeat(100000))).length();
        StringBuilder out = new StringBuilder("{\"version\":" + save.version + ",\"limit\":" + limit + ",\"npcs\":[");
        for (int i = 0; i < save.rows.size(); i++) {
            Row r = save.rows.get(i);
            if (i > 0) out.append(',');
            out.append("{\"id\":").append(quote(r.id)).append(",\"name\":").append(quote(r.name))
                .append(",\"profile\":").append(quote(r.profile)).append(",\"female\":").append(r.female)
                .append(",\"dead\":").append(r.dead).append('}');
        }
        return out.append("]}").toString();
    }
    public static void main(String[] args) {
        // Third-party initialization may print logs. Keep output and Unicode
        // independent of the Windows console code page; only JSON files are used.
        System.setOut(new PrintStream(OutputStream.nullOutputStream()));
        Path result = Path.of(args[2]);
        try {
            dataClass = Class.forName("npcfw.data.NPCData");
            loader = dataClass.getMethod("load", DataInputStream.class, int.class);
            limiter = dataClass.getMethod("limitProfile", String.class);
            byte[] bytes = Files.readAllBytes(Path.of(args[1]));
            Save save = parse(bytes);
            if (args[0].equals("patch")) {
                String profile = Files.readString(Path.of(args[4]), StandardCharsets.UTF_8);
                byte[] changed = patch(bytes, save, args[3], profile);
                Files.write(Path.of(args[5]), changed, StandardOpenOption.CREATE_NEW);
                save = parse(changed);
            } else if (!args[0].equals("inspect")) throw new IOException("UNKNOWN_COMMAND");
            Files.writeString(result, json(save), StandardCharsets.UTF_8);
        } catch (Throwable error) {
            try {
                String message = error.getMessage();
                if (message == null || !message.matches("[A-Z_]+")) message = "READER_INCOMPATIBLE";
                Files.writeString(result, "{\"error\":" + quote(message) + "}", StandardCharsets.UTF_8);
            } catch (Exception ignored) { }
            System.exit(1);
        }
    }
}
