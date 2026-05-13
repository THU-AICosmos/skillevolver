package com.example.catalogservice.config;

import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.userdetails.User;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

import java.util.Collections;
import java.util.HashMap;
import java.util.Map;

/**
 * In-memory user details service for the catalog service.
 * In a real application, this would connect to a user database.
 */
@Service
public class CatalogUserDetailsService implements UserDetailsService {

    private final Map<String, UserDetails> users = new HashMap<>();

    public CatalogUserDetailsService(PasswordEncoder passwordEncoder) {
        users.put("admin", new User("admin",
                passwordEncoder.encode("admin123"),
                true, true, true, true,
                Collections.singletonList(new SimpleGrantedAuthority("ROLE_ADMIN"))));

        users.put("manager", new User("manager",
                passwordEncoder.encode("manager123"),
                true, true, true, true,
                Collections.singletonList(new SimpleGrantedAuthority("ROLE_MANAGER"))));

        users.put("viewer", new User("viewer",
                passwordEncoder.encode("viewer123"),
                true, true, true, true,
                Collections.singletonList(new SimpleGrantedAuthority("ROLE_VIEWER"))));
    }

    @Override
    public UserDetails loadUserByUsername(String username) throws UsernameNotFoundException {
        UserDetails user = users.get(username);
        if (user == null) {
            throw new UsernameNotFoundException("User not found: " + username);
        }
        return user;
    }
}
