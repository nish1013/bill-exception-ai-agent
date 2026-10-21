public class Healthcheck {
    public static void main(String[] args) throws Exception {
        var url = new java.net.URL("http://localhost:8080/payables/.well-known/openid-configuration");
        var conn = (java.net.HttpURLConnection) url.openConnection();
        conn.setConnectTimeout(2000);
        conn.setReadTimeout(2000);
        System.exit(conn.getResponseCode() == 200 ? 0 : 1);
    }
}
