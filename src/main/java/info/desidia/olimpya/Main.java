package info.desidia.olimpya;

import info.desidia.olimpya.events.MessageListener;
import info.desidia.olimpya.events.ReadyEventListener;
import net.dv8tion.jda.api.JDA;
import net.dv8tion.jda.api.JDABuilder;

public class Main {
	public static void main(String[] args) throws Exception {
		JDA jda = JDABuilder.createDefault("MTIwMjIzNDg5MzU0ODEyNjIxOQ.GO95jT.4-ojVTJ4wKHXTUJaqRooAq77vhN3U9vIug7njU").build();
		jda.addEventListener(new MessageListener());

		jda.addEventListener(new ReadyEventListener());

	}

}