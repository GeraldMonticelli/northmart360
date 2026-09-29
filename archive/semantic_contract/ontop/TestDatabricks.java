import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.Statement;
import java.util.Properties;

public class TestDatabricks {

    public static void main(String[] args) throws Exception {

        Class.forName("com.databricks.client.jdbc.Driver");

        String url =
            "jdbc:databricks://adb-7405613337187597.17.azuredatabricks.net:443";

        Properties p = new Properties();

        p.put(
            "httpPath",
            "/sql/1.0/warehouses/400d6525fd91fee7"
        );

        p.put("AuthMech", "11");
        p.put("Auth_Flow", "2");
        p.put("TokenCachePassPhrase", "northmart-local-poc");
        p.put("EnableTokenCache", "0");

        try (
            Connection connection =
                DriverManager.getConnection(url, p);

            Statement statement =
                connection.createStatement();

            ResultSet result =
                statement.executeQuery(
                    "SELECT customer_id, first_name, birth_date " +
                    "FROM northmart_dev.crm.customer"
                )
        ) {

            while (result.next()) {

                System.out.println(
                    result.getString("customer_id")
                    + " | "
                    + result.getString("first_name")
                    + " | "
                    + result.getString("birth_date")
                );
            }
        }
    }
}