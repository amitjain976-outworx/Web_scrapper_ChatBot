import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import axios from "axios";


const API_BASE_URL = process.env.REACT_APP_API_BASE_URL;
const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(
    sessionStorage.getItem("access_token")
  );
  const [loading, setLoading] = useState(true);


  const api = useMemo(() => {
    const instance = axios.create({
      baseURL: API_BASE_URL,
    });

    instance.interceptors.request.use((config) => {
      const storedToken = sessionStorage.getItem("access_token");
      if (storedToken) {
        config.headers.Authorization = `Bearer ${storedToken}`;
      }
      return config;
    });

    return instance;
  }, []);


  useEffect(() => {
    const fetchUser = async () => {
      if (!token) {
        setLoading(false);
        return;
      }

      try {
        const res = await api.get("/auth/me");
        setUser(res.data);
      } catch (err) {
        console.error("Auth check failed", err);
        logout();
      } finally {
        setLoading(false);
      }
    };

    fetchUser();
  }, [token, api]);

  const login = async (username, password) => {
    const formData = new URLSearchParams();
    formData.append("username", username);
    formData.append("password", password);

    const res = await axios.post(
      `${API_BASE_URL}/auth/login`,
      formData,
      {
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
      }
    );

    const accessToken = res.data.access_token;

    sessionStorage.setItem("access_token", accessToken);
    setToken(accessToken);

    const me = await api.get("/auth/me");
    setUser(me.data);

    return me.data;
  };


  const signup = async (payload) => {
    // payload = { username, password, role }
    const res = await axios.post(
      `${API_BASE_URL}/auth/signup`,
      payload
    );
    return res.data;
  };


  const logout = () => {
    sessionStorage.removeItem("access_token");
    setToken(null);
    setUser(null);
  };


  const isAuthenticated = !!user;
  const isAdmin = user?.role === "admin";
  const isCustomer = user?.role === "customer";

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        loading,
        login,
        signup,
        logout,
        isAuthenticated,
        isAdmin,
        isCustomer,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};


export const useAuth = () => {
  return useContext(AuthContext);
};
