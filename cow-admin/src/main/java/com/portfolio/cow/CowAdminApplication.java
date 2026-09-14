package com.portfolio.cow;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
@MapperScan("com.portfolio.cow.modules.**.mapper")
public class CowAdminApplication {

    public static void main(String[] args) {
        SpringApplication.run(CowAdminApplication.class, args);
    }
}
