// Central API config
const API_BASE = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}/api/v1`
  : 'https://schemasense-api.onrender.com/api/v1'
 
export default API_BASE

console.log("ENV:", import.meta.env.VITE_API_URL);
console.log("API BASE:", API_BASE);