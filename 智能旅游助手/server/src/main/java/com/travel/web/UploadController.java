package com.travel.web;

import com.travel.common.BizException;
import com.travel.security.CurrentUser;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.security.SecureRandom;
import java.util.HexFormat;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.FileSystemResource;
import org.springframework.core.io.Resource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

/**
 * 图片上传与回读（任务书 2(4)：图片上传与本地存储）。
 *
 * <p>存本地目录而不是数据库：图片进库会让备份从几百 KB 变成几百 MB，
 * 而且每次渲染都要过一遍 JDBC。目录放在 {@code $DATA_DIR/uploads}，
 * 容器重建时随持久化卷一起留下。
 *
 * <p><b>回读接口是匿名可访问的</b>：{@code <img src>} 带不了自定义请求头，
 * 要鉴权就得把 token 拼进 URL 或走 fetch+blob，前者会漏进日志、后者要多写一堆代码。
 * 折中办法是文件名用 16 字节随机串——URL 不可猜，等于「知道链接才能看」。
 * 真要严格隔离，得换成带签名的临时链接，那是另一个量级的改造。
 */
@RestController
@RequestMapping("/api/uploads")
public class UploadController {

    private static final Set<String> ALLOWED = Set.of("jpg", "jpeg", "png", "webp", "gif");
    private static final SecureRandom RANDOM = new SecureRandom();
    private static final long MAX_BYTES = 5L * 1024 * 1024;

    private final Path dir;
    private final CurrentUser currentUser;

    public UploadController(
            @Value("${app.upload-dir:${DATA_DIR:./data}/uploads}") String dir, CurrentUser currentUser) {
        this.dir = Paths.get(dir).toAbsolutePath().normalize();
        this.currentUser = currentUser;
    }

    @PostMapping
    public Map<String, Object> upload(@RequestParam("file") MultipartFile file) {
        currentUser.require();
        if (file == null || file.isEmpty()) {
            throw BizException.badRequest("没有收到文件");
        }
        if (file.getSize() > MAX_BYTES) {
            throw BizException.badRequest("图片不能超过 5MB");
        }
        String ext = ext(file.getOriginalFilename());
        if (!ALLOWED.contains(ext)) {
            throw BizException.badRequest("只支持 jpg / png / webp / gif");
        }
        String type = file.getContentType();
        if (type == null || !type.toLowerCase(Locale.ROOT).startsWith("image/")) {
            throw BizException.badRequest("文件类型不是图片");
        }
        String name = HexFormat.of().formatHex(randomBytes(16)) + "." + ext;
        try {
            Files.createDirectories(dir);
            // 先写临时文件再原子改名：并发读的时候不会读到半个文件
            Path tmp = dir.resolve(name + ".part");
            try (var in = file.getInputStream()) {
                Files.copy(in, tmp, StandardCopyOption.REPLACE_EXISTING);
            }
            Files.move(tmp, dir.resolve(name), StandardCopyOption.ATOMIC_MOVE);
        } catch (IOException e) {
            throw new BizException("图片保存失败：" + e.getMessage());
        }
        return Map.of("url", "/api/uploads/" + name, "name", name, "size", file.getSize());
    }

    @GetMapping("/{name}")
    public ResponseEntity<Resource> get(@PathVariable String name) {
        // 只认「16 进制串 + 白名单后缀」，把 ../ 之类的东西挡在路径拼接之前
        if (!name.matches("^[0-9a-f]{16,64}\\.(jpg|jpeg|png|webp|gif)$")) {
            throw BizException.notFound("图片不存在");
        }
        Path p = dir.resolve(name).normalize();
        if (!p.startsWith(dir) || !Files.isRegularFile(p)) {
            throw BizException.notFound("图片不存在");
        }
        MediaType mt = switch (ext(name)) {
            case "png" -> MediaType.IMAGE_PNG;
            case "webp" -> MediaType.parseMediaType("image/webp");
            case "gif" -> MediaType.IMAGE_GIF;
            default -> MediaType.IMAGE_JPEG;
        };
        return ResponseEntity.ok()
                .contentType(mt)
                // 文件名是内容随机的，可以长期缓存；换图就是换 URL
                .header(HttpHeaders.CACHE_CONTROL, "public, max-age=31536000, immutable")
                .body(new FileSystemResource(p));
    }

    private static String ext(String filename) {
        if (filename == null) {
            return "";
        }
        int i = filename.lastIndexOf('.');
        return i < 0 ? "" : filename.substring(i + 1).toLowerCase(Locale.ROOT);
    }

    private static byte[] randomBytes(int n) {
        byte[] b = new byte[n];
        RANDOM.nextBytes(b);
        return b;
    }
}
