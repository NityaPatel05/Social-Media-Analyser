import axios from "axios";

const API_BASE = import.meta.env.VITE_API_URL || "http://35.169.145.225:8000";

const client = axios.create({
  baseURL: API_BASE,
  timeout: 60000,
});

export default client;
