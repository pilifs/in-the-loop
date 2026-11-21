package org.apache.commons.vfs2.provider.ftp;

import java.nio.file.*;
import org.apache.commons.vfs2.*;
import org.apache.commons.vfs2.impl.DefaultFileSystemManager;
import org.apache.commons.vfs2.util.FileObjectUtils;
import org.apache.ftpserver.FtpServer;
import org.apache.ftpserver.FtpServerFactory;
import org.apache.ftpserver.impl.DefaultFtpServer;
import org.apache.ftpserver.listener.ListenerFactory;
import org.apache.ftpserver.usermanager.PropertiesUserManagerFactory;
import org.apache.ftpserver.usermanager.impl.BaseUser;
import org.apache.ftpserver.ftplet.UserManager;

public final class UpgradeProbe {
    public static String observe(String[] args) throws Exception {
        Path root = Files.createDirectory(Paths.get("ftp-root"));
        Files.write(root.resolve("entry.dat"), new byte[] {1});
        Files.createDirectory(root.resolve("folder"));
        PropertiesUserManagerFactory config = new PropertiesUserManagerFactory();
        config.setFile(Files.createFile(Paths.get("users.properties")).toFile());
        UserManager accounts = config.createUserManager();
        BaseUser anonymous = new BaseUser();
        anonymous.setName("anonymous");
        anonymous.setHomeDirectory(root.toAbsolutePath().toString());
        accounts.save(anonymous);
        FtpServerFactory factory = new FtpServerFactory();
        factory.setUserManager(accounts);
        ListenerFactory binding = new ListenerFactory();
        binding.setServerAddress("127.0.0.1");
        binding.setPort(0);
        factory.addListener("default", binding.createListener());
        FtpServer server = factory.createServer();
        server.start();
        try {
            int port = ((DefaultFtpServer)server).getListener("default").getPort();
            DefaultFileSystemManager manager = new DefaultFileSystemManager();
            manager.addProvider("ftp", new FtpFileProvider());
            manager.setCacheStrategy(CacheStrategy.MANUAL);
            manager.init();
            try (FileObject file = manager.resolveFile("ftp://127.0.0.1:" + port + "/" + args[0])) {
                FtpFileObject actual = (FtpFileObject)FileObjectUtils.getAbstractFileObject(file);
                FileType type = actual.doGetType();
                return type == FileType.FILE ? "file" : type == FileType.FOLDER ? "folder" :
                       type == FileType.IMAGINARY ? "missing" : type.toString();
            } finally {
                manager.close();
            }
        } finally {
            server.stop();
        }
    }
}
