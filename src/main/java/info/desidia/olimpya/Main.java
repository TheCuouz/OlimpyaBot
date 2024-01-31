package info.desidia.olimpya;

import info.desidia.olimpya.events.MessageListener;
import info.desidia.olimpya.events.ReadyEventListener;
import net.dv8tion.jda.api.JDA;
import net.dv8tion.jda.api.JDABuilder;

public class Main {
	public static void main(String[] args) throws Exception {
		JDA jda = JDABuilder.createDefault("YOUR_BOT_TOKEN").build();
		jda.addEventListener(new MessageListener());

		jda.addEventListener(new ReadyEventListener());

	}

}